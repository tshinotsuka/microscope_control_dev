"""
qc_core.py -- UI-agnostic QC aggregator for one Grab's Data Recorder .h5
(+ optional ALS stem). The data spine for the Layer-2 QC dashboard.

One call (qc_load) returns everything the dashboard panels render, computed off
the already-verified loaders -- no plotting, no Qt, plain dicts:
    - injector TTL diagnosis           (diag_ttl logic: single / periodic / noisy)
    - inject -> cycle/frame mapping + head_pad   (datarecorder_loader timebase)
    - behavior channel summaries                 (every non-ttl/non-clock dataset)
    - ALS sweep quality (per-cycle pp)           (als_loader feedback, sweep_quality logic)

One-way import of the acquisition-repo loaders (numpy + h5py only):
    datarecorder_loader : .h5 -> samplerate, rising edges, frame/cycle timebase
    als_loader          : ALS 3-file -> scanner feedback (cycle, sample, ch) + meta

Conventions kept identical to the contract emitter (make_trigger_sync), so the
dashboard never disagrees with the frozen sidecar:
    * inject mapping uses '<=' (an edge ON a boundary belongs to the interval it
      STARTS) == searchsorted(edges, idx, 'right') == als_inject_align cycle #.
    * rate from the MEDIAN interval; recorder-start != frame/cycle-0 (head_pad).

CLI:
    python qc_core.py <recorder.h5>             # galvo/behavior/TTL QC
    python qc_core.py <recorder.h5> <als_stem>  # + ALS cycle timing & sweep QC
"""
from __future__ import annotations

import os

import numpy as np

import datarecorder_loader as DR


# --------------------------------------------------------------------------- #
# small primitives (shared convention with make_trigger_sync / als_inject_align)
# --------------------------------------------------------------------------- #
def _ttl_verdict(fs, edges, di_rel_tol=0.2):
    """diag_ttl-style classification of the injector channel."""
    if edges.size <= 1:
        return "single", "single (or no) edge -> clean injector pulse"
    di = np.diff(edges) / fs
    if di.std() < di_rel_tol * np.median(di):
        return ("periodic",
                f"periodic ~{1.0/np.median(di):.0f} Hz -> a clock / free-running "
                f"WG on this line, not a single injection pulse")
    return "noisy", "non-periodic transitions -> noise/pickup, or a pulse buried in noise"


def _inject_map(edges, idx, fs):
    """(index_1based, offset_ms) of the frame/cycle holding the edge.

    '<=' so an edge landing ON a boundary belongs to the interval it STARTS,
    identical to make_trigger_sync and to als_inject_align's
    searchsorted(edges, idx, side='right'). None if the edge precedes the clock.
    """
    if edges.size == 0 or idx is None:
        return None, None
    k = int(np.sum(edges <= idx))
    if not (0 < k <= edges.size):
        return None, None
    off_ms = (idx - edges[k - 1]) / fs * 1e3
    return k, round(float(off_ms), 3)


def _per_cycle_pp(scnnr):
    """(n_cycles,) 2D peak-to-peak from (n_cycles, samples, ch) scanner feedback.
    Same metric as sweep_quality.py; uses als_loader's verified array directly."""
    pp = np.ptp(scnnr, axis=1)                 # (n_cycles, nch)
    if pp.shape[1] >= 2:
        return np.hypot(pp[:, 0], pp[:, 1])
    return pp[:, 0]


def _commanded_cycles(si):
    v = si.get("hStackManager.framesPerSlice")
    try:
        v = int(v)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# the one call the dashboard makes
# --------------------------------------------------------------------------- #
def qc_load(h5_path, als_stem=None, ttl_name="Legato130_TTL", clock_name="frame_clock"):
    """Aggregate QC for one Grab. Returns a plain dict (see module docstring)."""
    data = DR.load_datarecorder(h5_path)
    fs = data["samplerate"]
    out = {
        "file": os.path.basename(h5_path),
        "samplerate_hz": fs,
        "datasets": list(data["names"]),
        "injector": None,
        "timing": None,
        "behavior": [],
        "sweep": None,
        "warnings": [],
    }
    if fs is None:
        out["warnings"].append("no root '/' attribute 'samplerate'")
        return out

    # --- injector TTL (t0 + diagnosis) ---
    inj_idx = None
    if ttl_name in data["signals"]:
        x = data["signals"][ttl_name]
        edges = DR.rising_edges(x)
        if edges.size:
            inj_idx = int(edges[0])
        vk, vmsg = _ttl_verdict(fs, edges)
        out["injector"] = {
            "dataset": ttl_name,
            "t0_recorder_s": (None if inj_idx is None else round(inj_idx / fs, 4)),
            "sample_index": inj_idx,
            "n_edges": int(edges.size),
            "range_v": [round(float(x.min()), 3), round(float(x.max()), 3)],
            "verdict": vk,
            "verdict_msg": vmsg,
        }
    else:
        out["warnings"].append(f"injector dataset {ttl_name!r} absent")

    # --- timing: ALS cycle (als_stem given) / galvo frame, from the clock dataset ---
    if clock_name in data["signals"]:
        fb = DR.frame_timebase(data, clock_name)
        is_als = als_stem is not None
        k, off = _inject_map(fb["edges"], inj_idx, fs)
        out["timing"] = {
            "mode": "als" if is_als else "galvo",
            "clock_dataset": clock_name,
            "n": int(fb["n_frames"]),                       # cycles (ALS) / frames (galvo)
            "rate_hz": (None if not np.isfinite(fb["rate_hz"]) else round(fb["rate_hz"], 3)),
            "head_pad_s": (None if not np.isfinite(fb["head_pad_s"]) else round(fb["head_pad_s"], 4)),
            "tail_pad_s": (None if not np.isfinite(fb["tail_pad_s"]) else round(fb["tail_pad_s"], 4)),
            "inject_index_1based": k,                        # cycle # (ALS) / frame # (galvo)
            "inject_offset_ms": off,
            "n_commanded": None,
        }
    else:
        msg = f"clock dataset {clock_name!r} absent"
        out["warnings"].append(msg + (" (expected for ALS only if branch-A clock not looped)"
                                      if als_stem else ""))

    # --- behavior = every dataset that is not the ttl or the clock ---
    for name in data["names"]:
        if name in (ttl_name, clock_name):
            continue
        v = data["signals"][name]
        out["behavior"].append({
            "name": name,
            "n": int(v.size),
            "min": round(float(v.min()), 4),
            "max": round(float(v.max()), 4),
            "mean": round(float(v.mean()), 4),
            "range_v": [round(float(v.min()), 3), round(float(v.max()), 3)],
        })

    # --- ALS sweep quality + cross-stream cycle-count check (als_loader) ---
    if als_stem is not None:
        try:
            import als_loader as AL
            ls = AL.load(als_stem)
            pmt_n = int(ls.pmt.shape[0]) if ls.pmt is not None else None
            scn_n = int(ls.scnnr.shape[0]) if ls.scnnr is not None else None
            if out["timing"] is not None:
                out["timing"]["n_commanded"] = _commanded_cycles(ls.si)

            if ls.scnnr is not None:
                pp = _per_cycle_pp(ls.scnnr)
                pct = np.percentile(pp, [0, 5, 25, 50, 75, 95, 100])
                p05, p50 = float(pct[1]), float(pct[3])
                ok = (p05 > 0) and (p05 >= 0.5 * p50)
                out["sweep"] = {
                    "n_cycles": int(pp.size),                # scnnr cycles
                    "n_cycles_pmt": pmt_n,
                    "pp_percentiles": [round(float(p), 4) for p in pct],
                    "median_over_5th": (round(p50 / p05, 3) if p05 > 0 else None),
                    "verdict": "PASS" if ok else "CHECK",
                    "first10": [round(float(v), 4) for v in pp[:10]],
                    "last10": [round(float(v), 4) for v in pp[-10:]],
                }
            else:
                out["warnings"].append("ALS feedback off / .scnnr.dat absent -> no sweep QC")

            # cross-check the four independent cycle counts (pmt / scnnr / clock / commanded).
            # they SHOULD agree (±1 boundary); a wider gap means one stream is clipped
            # (e.g. feedback DMA stops early) -> per-cycle pmt<->feedback alignment is offset.
            counts = {"pmt": pmt_n, "scnnr": scn_n,
                      "clock": (out["timing"]["n"] if out["timing"] else None),
                      "commanded": (out["timing"]["n_commanded"] if out["timing"] else None)}
            present = {k: v for k, v in counts.items() if v is not None}
            out["cycle_counts"] = present
            if present and (max(present.values()) - min(present.values()) > 1):
                out["warnings"].append(
                    "cycle-count mismatch across streams " + str(present) +
                    " -> pmt<->feedback per-cycle alignment may be offset (likely a "
                    "tail-clipped stream); check which end the missing cycles are on.")
        except FileNotFoundError as e:
            out["warnings"].append(f"ALS files not found for sweep QC: {e}")
        except Exception as e:                              # noqa: BLE001 (keep QC robust)
            out["warnings"].append(f"ALS sweep QC skipped: {type(e).__name__}: {e}")

    return out


def summarize(h5_path, als_stem=None):
    """Console one-shot; the dashboard renders the very same dict."""
    q = qc_load(h5_path, als_stem)
    print(f"file        : {q['file']}  ({q['samplerate_hz']} Hz)  datasets={q['datasets']}")
    inj = q["injector"]
    if inj:
        print(f"injector    : t0={inj['t0_recorder_s']} s  edges={inj['n_edges']}  "
              f"[{inj['verdict']}] {inj['verdict_msg']}")
    t = q["timing"]
    if t:
        lbl = "cycle" if t["mode"] == "als" else "frame"
        nc = f"/{t['n_commanded']}" if t["n_commanded"] else ""
        print(f"timing      : {t['mode']}  {t['n']}{nc} {lbl}s @ {t['rate_hz']} Hz  "
              f"head_pad={t['head_pad_s']} s  inject@{lbl} #{t['inject_index_1based']} "
              f"(+{t['inject_offset_ms']} ms)")
    if q["sweep"]:
        s = q["sweep"]
        print(f"sweep       : {s['n_cycles']} cyc  median/5th={s['median_over_5th']}  [{s['verdict']}]")
    for b in q["behavior"]:
        print(f"behavior    : {b['name']}  range {b['range_v']}  mean {b['mean']}  (n={b['n']})")
    for w in q["warnings"]:
        print(f"  ! {w}")
    return q


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python qc_core.py <recorder.h5> [als_stem]")
        sys.exit(1)
    summarize(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
