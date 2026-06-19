#!/usr/bin/env python3
"""
als_inject_align.py — align the recorded injector t0 to the ALS imaging timeline
and measure the residual offset (the ALS-mode "head_pad").

This is the analysis side of go/no-go ③ for the ALS bench
(method_a_als_bench_runsheet §0/§7.2): map the recorder-relative injector TTL edge
onto ALS cycles/lines, and produce the residual offset
    residual = recorder-start - ALS-acquisition-start
which is the ALS analogue of the galvo head_pad (1.975 s @ galvo, datarecorder_loader).

Sibling of compare_als_ref.py / make_trigger_sync.py. One-way import of the two
acquisition-repo loaders (numpy + h5py only):
    datarecorder_loader : Data Recorder .h5  -> samplerate, injector edge, clock edges
    als_loader          : ALS .meta.txt      -> cycle period, n_cycles, segments

Two anchoring branches (the schema anchor is 'als_datafile_timing' either way):

  BRANCH A  (preferred) — an ALS period/line clock is recorded in the .h5
      ScanImage's frame-clock-out fires once per cycle in line-scan mode
      (each cycle = one internal "frame": lineScanSamplesPerFrame / framesPerSlice),
      so the EXISTING D0.0->AI6 loopback may already carry it. If so this is a
      DIRECT MEASUREMENT, exactly like galvo frame_clock:
          residual = first clock edge / fs
      and the injection maps to a specific cycle (and line, via segment_samples).

  BRANCH B  (fallback) — no clock (clock dataset absent or flat)
      We must assume recorder-start == ALS-acquisition-start (common acq-start).
      Then residual is UNMEASURED, and the cycle index is uncertain by
      residual / cycle_duration cycles (~hundreds for a ~2 s head_pad at 4 ms
      cycles). Branch B can only place the injection in *seconds-into-recording*,
      not in a specific cycle. Prefer branch A.

Usage:
    # quicklook (meta + .h5 only; numpy+h5py)
    python als_inject_align.py <recorder.h5> <als_stem-or-meta.txt>
    # name a different clock signal (if a dedicated ALS clock was wired)
    python als_inject_align.py <recorder.h5> <als_stem> --clock-name als_period_clock
    # also emit a schema-valid trigger_sync sidecar (DELEGATES to make_trigger_sync,
    # which self-computes the v0.2.0 als_datafile_timing block from the branch-A clock):
    python als_inject_align.py <recorder.h5> <als_stem> --emit-sidecar --out sync.json
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np

import als_loader as AL
import datarecorder_loader as DR

RATE_TOL = 0.02   # relative tolerance for matching observed clock rate to expected


# --------------------------------------------------------------------------- #
# meta-derived ALS timing
# --------------------------------------------------------------------------- #
@dataclass
class AlsTiming:
    stem: str
    cycle_duration_s: float
    cycle_rate_hz: float
    pmt_sample_rate: float
    fdbk_sample_rate: float
    pmt_samples_per_cycle: int
    fdbk_samples_per_cycle: int
    n_cycles: int | None            # from framesPerSlice (single-slice ALS)
    lines_per_cycle: int            # count of 'line' scanfields in one cycle
    segments: list[dict] = field(default_factory=list)   # segment_samples output

    @property
    def als_total_s(self) -> float | None:
        return None if self.n_cycles is None else self.n_cycles * self.cycle_duration_s

    @property
    def line_rate_hz(self) -> float:
        return self.cycle_rate_hz * max(self.lines_per_cycle, 1)


def _resolve_meta(path: str) -> tuple[str, str]:
    """Return (meta_path, stem). Accepts a stem, '<stem>.meta.txt', or the
    upload-style '<stem>_meta.txt'. Only the meta is needed (no .dat)."""
    for suf in (".meta.txt", "_meta.txt"):
        if path.endswith(suf):
            return path, path[: -len(suf)]
    cand = path + ".meta.txt"
    if os.path.isfile(cand):
        return cand, path
    if os.path.isfile(path):           # some other readable meta file
        return path, os.path.splitext(path)[0]
    return cand, path                  # let parse_meta raise a clear error


def als_timing(als_stem: str) -> AlsTiming:
    meta_path, stem = _resolve_meta(als_stem)
    si, roi = AL.parse_meta(meta_path)
    info = AL.acq_info(si)
    seg = AL.segment_samples(si, roi)
    line_segs = [s for s in seg["segments"]
                 if str(s.get("function") or "").endswith("line")]
    n_cyc = si.get("hStackManager.framesPerSlice")
    n_cyc = int(n_cyc) if isinstance(n_cyc, (int, float)) and np.isfinite(n_cyc) else None
    return AlsTiming(
        stem=stem,
        cycle_duration_s=info.cycle_duration_s,
        cycle_rate_hz=info.cycle_rate_hz,
        pmt_sample_rate=info.pmt_sample_rate,
        fdbk_sample_rate=info.fdbk_sample_rate,
        pmt_samples_per_cycle=info.pmt_samples_per_cycle,
        fdbk_samples_per_cycle=info.fdbk_samples_per_cycle,
        n_cycles=n_cyc,
        lines_per_cycle=len(line_segs) if line_segs else 1,
        segments=seg["segments"],
    )


# --------------------------------------------------------------------------- #
# within-cycle localization
# --------------------------------------------------------------------------- #
def _segment_at_pmt(timing: AlsTiming, pmt_sample: int) -> str:
    for s in timing.segments:
        a, b = s["pmt"]
        if a <= pmt_sample < b:
            fn = str(s.get("function") or "").split(".")[-1]
            return f'{s["name"]} ({fn})' if fn else str(s["name"])
    return "leftover/transition"


def _rel(a: float, b: float) -> float:
    return abs(a - b) / b if b else float("inf")


# --------------------------------------------------------------------------- #
# core
# --------------------------------------------------------------------------- #
def align_injection(
    h5_path: str,
    als_stem: str,
    clock_name: str = "frame_clock",
    ttl_name: str = "Legato130_TTL",
    thresh: float | None = None,
) -> dict:
    """Align injector t0 onto the ALS timeline. Returns a structured result dict."""
    timing = als_timing(als_stem)
    data = DR.load_datarecorder(h5_path)
    fs = data["samplerate"]
    if fs is None:
        raise ValueError(f"{h5_path}: no root '/' attribute 'samplerate'")
    if ttl_name not in data["signals"]:
        raise ValueError(f"injector dataset {ttl_name!r} absent; have {data['names']}")

    # injector edge (recorder-relative t0 = analysis time-zero)
    inj_edges = DR.rising_edges(data["signals"][ttl_name], thresh)
    if inj_edges.size == 0:
        raise ValueError(f"no rising edge in injector dataset {ttl_name!r}")
    inj_idx = int(inj_edges[0])
    t0_recorder_s = inj_idx / fs

    res: dict[str, Any] = {
        "recorder_file": os.path.basename(h5_path),
        "als_stem": os.path.basename(timing.stem),
        "samplerate_hz": float(fs),
        "recorder_total_s": round(data["signals"][ttl_name].size / fs, 4),
        "injector": {
            "dataset": ttl_name,
            "sample_index": inj_idx,
            "t0_recorder_s": round(t0_recorder_s, 4),
            "n_edges": int(inj_edges.size),
        },
        "als": {
            "cycle_duration_ms": round(timing.cycle_duration_s * 1e3, 6),
            "cycle_rate_hz": round(timing.cycle_rate_hz, 4),
            "line_rate_hz": round(timing.line_rate_hz, 4),
            "n_cycles_meta": timing.n_cycles,
            "lines_per_cycle": timing.lines_per_cycle,
            "als_total_s": (None if timing.als_total_s is None
                            else round(timing.als_total_s, 4)),
        },
    }

    # is a usable clock present?
    clk = data["signals"].get(clock_name)
    clk_edges = DR.rising_edges(clk, thresh) if clk is not None else np.array([], int)

    if clk_edges.size >= 2:
        res.update(_branch_a(timing, fs, inj_idx, clock_name, clk_edges))
    else:
        why = ("absent" if clk is None else
               "flat (no edges — ALS frame-clock-out not firing on this line)")
        res.update(_branch_b(timing, fs, inj_idx, t0_recorder_s, clock_name, why))
    return res


def _branch_a(timing, fs, inj_idx, clock_name, edges) -> dict:
    obs_rate = 1.0 / float(np.median(np.diff(edges) / fs))
    head_pad = edges[0] / fs                      # residual offset = ALS head_pad
    n_edges = int(edges.size)

    # detect granularity: per-cycle vs per-line
    match_cycle = _rel(obs_rate, timing.cycle_rate_hz)
    match_line = _rel(obs_rate, timing.line_rate_hz)
    if min(match_cycle, match_line) > RATE_TOL:
        granularity, rate_match = "unknown", False
    elif match_cycle <= match_line:
        granularity, rate_match = "cycle", True
    else:
        granularity, rate_match = "line", True

    # containing index (0-based) of the clock interval holding the injection edge.
    # side='right' => an edge landing ON a boundary belongs to the cycle it STARTS
    # (cycle_number_1based = searchsorted(edges, idx, 'right'); make_trigger_sync's
    # '<=' boundary convention is provably identical).
    i0 = int(np.searchsorted(edges, inj_idx, side="right") - 1)
    if i0 < 0:
        # injection precedes the first clock edge (inside head_pad, before ALS start)
        cycle0 = line_in_cycle = None
        offset_s = (inj_idx - 0) / fs            # relative to recorder start
        pmt_sample = fdbk_sample = None
        within = "before first cycle (during head_pad)"
    else:
        offset_s = (inj_idx - edges[i0]) / fs    # in [0, interval)
        if granularity == "line":
            lpc = max(timing.lines_per_cycle, 1)
            cycle0, line_in_cycle = divmod(i0, lpc)
            # offset is within a line; place within the cycle using the line's pmt start
            line_pmt_start = (timing.segments[line_in_cycle]["pmt"][0]
                              if line_in_cycle < len(timing.segments) else 0)
            pmt_sample = line_pmt_start + int(round(offset_s * timing.pmt_sample_rate))
        else:  # cycle (or unknown -> treat as cycle)
            cycle0, line_in_cycle = i0, None
            pmt_sample = int(round(offset_s * timing.pmt_sample_rate))
        fdbk_sample = int(round(offset_s * timing.fdbk_sample_rate)) if timing.fdbk_sample_rate else None
        within = _segment_at_pmt(timing, pmt_sample) if pmt_sample is not None else "?"

    # cross-checks
    expected_n = (timing.n_cycles if granularity != "line"
                  else (None if timing.n_cycles is None
                        else timing.n_cycles * max(timing.lines_per_cycle, 1)))
    count_match = (expected_n is not None and abs(n_edges - expected_n) <= 1)
    clock_span_s = (edges[-1] - edges[0]) / fs + (1.0 / obs_rate)

    return {
        "branch": "A_clock",
        "anchor": "als_datafile_timing",
        "residual_offset_s": round(float(head_pad), 4),   # the headline ③ number
        "clock": {
            "dataset": clock_name,
            "granularity": granularity,
            "observed_rate_hz": round(obs_rate, 4),
            "n_edges": n_edges,
            "expected_n_edges": expected_n,
            "rate_match": rate_match,
            "count_match": bool(count_match),
            "clock_span_s": round(float(clock_span_s), 4),
        },
        "inject_map": {
            "cycle_index_0based": cycle0,
            "cycle_number_1based": (None if cycle0 is None else cycle0 + 1),
            "line_in_cycle_0based": line_in_cycle,
            "offset_into_interval_ms": round(float(offset_s) * 1e3, 4),
            "pmt_sample_in_cycle": pmt_sample,
            "fdbk_sample_in_cycle": fdbk_sample,
            "within_cycle": within,
        },
        "warnings": _branch_a_warnings(timing, fs, obs_rate, rate_match, count_match,
                                       clock_span_s, granularity),
    }


def _branch_a_warnings(timing, fs, obs_rate, rate_match, count_match, span, granularity):
    w = []
    if not rate_match:
        w.append(
            f"clock rate {obs_rate:.3f} Hz matches neither cycle "
            f"({timing.cycle_rate_hz:.3f}) nor line ({timing.line_rate_hz:.3f}) — "
            f"is this really the ALS clock, or a stale/galvo frame clock?")
    if not count_match and timing.n_cycles is not None:
        w.append("clock edge count does not match meta cycle/line count (±1).")
    if timing.als_total_s and _rel(span, timing.als_total_s) > 0.01:
        w.append(f"clock span {span:.3f}s vs ALS total {timing.als_total_s:.3f}s differ >1%.")
    if obs_rate > 0.4 * fs:
        w.append(f"clock rate {obs_rate:.1f} Hz is >40% of fs {fs:.0f} Hz — "
                 f"under-sampled; raise Data Recorder Sample Rate.")
    if granularity == "unknown":
        w.append("granularity undetermined; cycle mapping assumed per-cycle.")
    return w


def _branch_b(timing, fs, inj_idx, t0_recorder_s, clock_name, why) -> dict:
    # assume recorder-start == ALS-acquisition-start (common acq-start). residual UNMEASURED.
    cycle0 = int(np.floor(t0_recorder_s / timing.cycle_duration_s))
    offset_s = t0_recorder_s - cycle0 * timing.cycle_duration_s
    pmt_sample = int(round(offset_s * timing.pmt_sample_rate))
    fdbk_sample = int(round(offset_s * timing.fdbk_sample_rate)) if timing.fdbk_sample_rate else None
    within = _segment_at_pmt(timing, pmt_sample)
    in_range = (timing.als_total_s is None) or (0.0 <= t0_recorder_s <= timing.als_total_s)

    warnings = [
        f"no usable clock on {clock_name!r} ({why}); using common acq-start approximation.",
        "residual offset is UNMEASURED: recorder-start assumed == ALS-acq-start.",
    ]
    if not in_range:
        warnings.append("injector t0 falls outside [0, ALS total] — alignment inconsistent.")

    return {
        "branch": "B_common_acq_start",
        "anchor": "als_datafile_timing",
        "residual_offset_s": None,            # cannot be measured without a clock
        "clock": {"dataset": clock_name, "present": False},
        "inject_map": {
            "cycle_index_0based": cycle0,
            "cycle_number_1based": cycle0 + 1,
            "line_in_cycle_0based": None,
            "offset_into_interval_ms": round(float(offset_s) * 1e3, 4),
            "pmt_sample_in_cycle": pmt_sample,
            "fdbk_sample_in_cycle": fdbk_sample,
            "within_cycle": within,
            "_assumes_zero_head_pad": True,
        },
        "cycle_index_uncertainty_note": (
            "true cycle = floor((t0 - head_pad)/T_cyc); with head_pad unknown the "
            f"index is uncertain by head_pad/{timing.cycle_duration_s*1e3:g}ms cycles "
            "(e.g. ~494 cycles for a 1.975 s head_pad). Use branch A for cycle resolution."),
        "warnings": warnings,
    }


# --------------------------------------------------------------------------- #
# reporting / sidecar
# --------------------------------------------------------------------------- #
def report(res: dict) -> str:
    L = []
    a = res["injector"]; al = res["als"]
    L.append(f"recorder    : {res['recorder_file']}  ({res['recorder_total_s']} s @ {res['samplerate_hz']:g} Hz)")
    L.append(f"als         : {res['als_stem']}  cycle {al['cycle_duration_ms']} ms "
             f"({al['cycle_rate_hz']} Hz), {al['n_cycles_meta']} cyc x {al['lines_per_cycle']} line "
             f"= {al['als_total_s']} s")
    L.append(f"injector t0 : {a['t0_recorder_s']} s (sample {a['sample_index']}, {a['n_edges']} edge) recorder-relative")
    L.append(f"branch      : {res['branch']}   anchor={res['anchor']}")
    if res["branch"].startswith("A"):
        c = res["clock"]; m = res["inject_map"]
        ok = "OK" if (c["rate_match"] and c["count_match"]) else "CHECK"
        L.append(f"clock       : '{c['dataset']}' {c['granularity']} @ {c['observed_rate_hz']} Hz, "
                 f"{c['n_edges']}/{c['expected_n_edges']} edges  [{ok}]")
        L.append(f"RESIDUAL    : {res['residual_offset_s']} s   <-- ALS head_pad (go/no-go ③)")
        L.append(f"inject map  : cycle #{m['cycle_number_1based']} "
                 + (f"line {m['line_in_cycle_0based']} " if m['line_in_cycle_0based'] is not None else "")
                 + f"(+{m['offset_into_interval_ms']} ms) -> pmt sample {m['pmt_sample_in_cycle']}, "
                 f"in {m['within_cycle']}")
    else:
        m = res["inject_map"]
        L.append("clock       : none -> common acq-start approximation")
        L.append("RESIDUAL    : UNMEASURED (no clock)")
        L.append(f"inject map  : ~cycle #{m['cycle_number_1based']} (+{m['offset_into_interval_ms']} ms) "
                 f"assuming head_pad=0  [uncertain]")
    for w in res.get("warnings", []):
        L.append(f"  ! {w}")
    if "cycle_index_uncertainty_note" in res:
        L.append(f"  i {res['cycle_index_uncertainty_note']}")
    return "\n".join(L)


def emit_sidecar(h5_path: str, als_stem: str, res: dict,
                 clock_name: str = "frame_clock",
                 ttl_name: str = "Legato130_TTL") -> dict:
    """Emit the schema-valid trigger_sync sidecar by DELEGATING to the single
    contract emitter (make_trigger_sync). make_trigger_sync self-computes the
    v0.2.0 als_datafile_timing block from the branch-A clock (source
    'als_branch_a_clock', head_pad_s, inject_cycle via the '<=' boundary
    convention, which is provably identical to this module's branch-A mapping:
    cycle_1based == searchsorted(edges, idx, 'right')).

    The richer within-cycle diagnostics (which ROI, pmt sample) live in
    report()/--json; they are NOT part of the frozen contract sidecar.

    `res` is accepted to pass through the commanded cycle count
    (n_cycles_commanded) for the cross-check field; alignment itself is recomputed
    inside make_trigger_sync from the same recorded clock, so the two paths agree.
    """
    import make_trigger_sync as MTS
    _, stem = _resolve_meta(als_stem)
    return MTS.build_trigger_sync(
        h5_path, "als",
        als_datafile=os.path.basename(stem),
        n_cycles_commanded=res["als"]["n_cycles_meta"],
        ttl_name=ttl_name,
        fc_name=clock_name,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="align injector t0 to the ALS timeline (go/no-go ③)")
    ap.add_argument("h5")
    ap.add_argument("als_stem", help="ALS stem or path to its .meta.txt")
    ap.add_argument("--clock-name", default="frame_clock",
                    help="recorder dataset carrying the ALS cycle/line clock (default: frame_clock)")
    ap.add_argument("--ttl-name", default="Legato130_TTL")
    ap.add_argument("--json", action="store_true", help="print the full result dict as JSON")
    ap.add_argument("--emit-sidecar", action="store_true",
                    help="also emit a schema-valid trigger_sync sidecar (delegates to make_trigger_sync)")
    ap.add_argument("--out", default=None, help="write emitted sidecar JSON here")
    a = ap.parse_args()

    res = align_injection(a.h5, a.als_stem, clock_name=a.clock_name, ttl_name=a.ttl_name)
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(report(res))
    if a.emit_sidecar or a.out:
        sc = emit_sidecar(a.h5, a.als_stem, res, clock_name=a.clock_name, ttl_name=a.ttl_name)
        text = json.dumps(sc, indent=2, ensure_ascii=False)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            print(f"\n[write] {a.out}")
        else:
            print("\n" + text)


if __name__ == "__main__":
    main()
