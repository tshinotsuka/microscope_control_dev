#!/usr/bin/env python3
"""
make_trigger_sync.py -- emit a schema-valid trigger_sync sidecar from a Data
Recorder .h5, and (optionally) validate it against trigger_sync.schema.json.

Sibling of make_sidecar.py (als_sidecar). One-way import of the acquisition-repo
loader: reads the .h5 with datarecorder_loader, derives injection t0 (the recorded
TTL edge = analysis time-zero) and the imaging timebase:
    galvo / resonant : frame_timebase from the frame_clock dataset
    als              : als_datafile_timing from the branch-A clock = the SAME
                       frame_clock dataset (D0.0->AI6 loopback emits one rising
                       edge per ALS cycle), but signals.frame_clock is null and
                       anchor='als_datafile_timing' (per schema then-branch).

0.3.0 (C2, method A): also emits 'recorded_channels' -- the full physical
inventory of the .h5 (every dataset: name / AI / role / measured range) so the
sidecar self-describes behavior + sync. behavior_sidecar (method B) is deprecated.

This is the SINGLE schema-conformant trigger_sync emitter. als_inject_align.py's
rich console analysis (which ROI, pmt sample) is diagnostics only; for the
contract sidecar it should delegate here rather than build its own dict.

scan_mode -> anchor (enforced by the schema's allOf, mirrored here):
    galvo / resonant : anchor='frame_clock'        + frame_timebase        (required)
    als              : anchor='als_datafile_timing' + als_datafile          (required)
                                                    + als_datafile_timing   (required)

Usage:
    python make_trigger_sync.py <h5> galvo  [--schema trigger_sync.schema.json] [--out s.json]
    python make_trigger_sync.py <h5> als    --als-datafile <stem>
                                            [--n-cycles-commanded 1000]
                                            [--schema ...] [--out ...]
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np

import datarecorder_loader as DR

SCHEMA_VERSION = "0.3.0"   # 0.2.0 -> 0.3.0 at C2 (recorded_channels block; method A)

# name -> (physical vDAQ AI, controlled-vocab role). ADDITIVE: to add a new stream
# (e.g. "pupil_area": ("AI3", "pupil")) add it here AND to the schema role enum.
ROLE_MAP = {
    "Legato130_TTL":   ("AI7", "injector_trigger"),
    "frame_clock":     ("AI6", "cycle_clock"),
    "treadmill_dir":   ("AI4", "locomotion_direction"),
    "treadmill_speed": ("AI5", "locomotion_speed"),
}

# stable emit order for recorded_channels (sync first, then behavior)
_ROLE_ORDER = {"injector_trigger": 0, "cycle_clock": 1,
               "locomotion_speed": 2, "locomotion_direction": 3}


def _round(x, n):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


def _recorded_channels(data, role_map=ROLE_MAP):
    """Full physical inventory of the .h5 -> (channels, n_samples).

    Fails LOUD on an unmapped dataset (deliberate, like schema_version const): a
    new recorded stream must be added to ROLE_MAP (and the schema role enum)
    before it can be emitted, rather than slipping through undocumented.
    """
    chans, n = [], 0
    for name, arr in data["signals"].items():
        a = np.asarray(arr, dtype=float)
        n = max(n, int(a.size))
        if name not in role_map:
            raise ValueError(
                f"unmapped recorded channel {name!r}; add it to ROLE_MAP (and the "
                f"schema role enum) before emitting. present: {data['names']}")
        ai, role = role_map[name]
        chans.append({
            "name": name,
            "ai": ai,
            "role": role,
            "units": "V",
            "range_v": [_round(float(np.nanmin(a)), 6), _round(float(np.nanmax(a)), 6)],
        })
    chans.sort(key=lambda c: (_ROLE_ORDER.get(c["role"], 9), c["name"]))
    return chans, n


def build_trigger_sync(
    h5_path: str,
    scan_mode: str,
    als_datafile: str | None = None,
    n_cycles_commanded: int | None = None,
    ttl_name: str = "Legato130_TTL",
    fc_name: str = "frame_clock",
    edge: str = "rising",
    schema_version: str = SCHEMA_VERSION,
) -> dict:
    if scan_mode not in ("galvo", "als", "resonant"):
        raise ValueError(f"scan_mode must be galvo|als|resonant, got {scan_mode!r}")
    if scan_mode == "als" and not als_datafile:
        raise ValueError("scan_mode 'als' requires als_datafile (the ALS stem)")

    data = DR.load_datarecorder(h5_path)
    fs = data["samplerate"]
    if fs is None:
        raise ValueError(f"{h5_path}: no root '/' attribute 'samplerate'")
    if ttl_name not in data["signals"]:
        raise ValueError(f"injector dataset {ttl_name!r} not in {data['names']}")

    # --- full channel inventory (C2, method A) -------------------------------
    recorded, n_samples = _recorded_channels(data)

    # --- injection t0 = recorded TTL edge (scan-mode independent) -------------
    ttl = data["signals"][ttl_name]
    lo, hi = float(np.nanmin(ttl)), float(np.nanmax(ttl))
    thresh = 0.5 * (lo + hi)
    t0_s, idx, n_edges = DR.injector_t0(data, ttl_name, thresh)
    if t0_s is None:
        raise ValueError(f"no {edge} edge found in {ttl_name!r}")

    sidecar: dict = {
        "schema_version": schema_version,
        "scan_mode": scan_mode,
        "samplerate_hz": float(fs),
        "n_samples": int(n_samples),
        "datarecorder_file": os.path.basename(h5_path),
        # basename only (raw/-relative stem), matching datarecorder_file -- an
        # absolute path would break when the sidecar moves to NAS/another machine.
        "als_datafile": (os.path.basename(als_datafile)
                         if (scan_mode == "als" and als_datafile) else None),
        "signals": {
            "injector_ttl": ttl_name,
            # ALS: frame_clock dataset exists physically but is the branch-A cycle
            # clock, NOT a galvo frame clock -> reported null per schema. (It is
            # still listed in recorded_channels with role 'cycle_clock'.)
            "frame_clock": (fc_name if (scan_mode != "als" and fc_name in data["signals"]) else None),
        },
        "recorded_channels": recorded,
        "t0": {
            "source": "datarecorder_ttl_edge",
            "dataset": ttl_name,
            "edge": edge,
            "threshold_v": _round(thresh, 3),
            "sample_index": int(idx),
            "t0_recorder_s": _round(t0_s, 4),
            "n_edges": int(n_edges),
        },
        "anchor": "als_datafile_timing" if scan_mode == "als" else "frame_clock",
        "physical_delay_offset_s": None,
    }

    if scan_mode != "als":
        # --- frame timebase (galvo/resonant) ---------------------------------
        if fc_name not in data["signals"]:
            raise ValueError(
                f"scan_mode {scan_mode!r} needs frame_clock dataset {fc_name!r}; "
                f"present: {data['names']}"
            )
        fb = DR.frame_timebase(data, fc_name)
        if fb["n_frames"] < 1:
            raise ValueError(f"no frame edges in {fc_name!r}")
        inject_frame = None
        inject_off_ms = None
        edges = fb["edges"]
        # '<=' so an edge landing ON a boundary belongs to the frame it STARTS
        # (deterministic injection lands at +0.0 ms boundaries; matches als_inject_align).
        k = int(np.sum(edges <= idx))
        if 0 < k <= edges.size:
            inject_frame = k
            inject_off_ms = _round((idx - edges[k - 1]) / fs * 1000.0, 1)
        sidecar["frame_timebase"] = {
            "source": "frame_clock",
            "n_frames": int(fb["n_frames"]),
            "rate_hz": _round(fb["rate_hz"], 2),
            "head_pad_s": _round(fb["head_pad_s"], 3),
            "tail_pad_s": _round(fb["tail_pad_s"], 3),
            "inject_frame": inject_frame,
            "inject_offset_into_frame_ms": inject_off_ms,
        }
    else:
        # --- ALS cycle timing: branch-A clock = the frame_clock dataset -------
        # (D0.0->AI6 loopback emits one rising edge per ALS cycle). Same edge
        # math as frame_timebase, stored under the ALS block with cycle terms.
        if fc_name not in data["signals"]:
            raise ValueError(
                f"ALS needs the branch-A clock dataset {fc_name!r} (D0.0->AI6 loopback); "
                f"present: {data['names']}"
            )
        cb = DR.frame_timebase(data, fc_name)  # one rising edge per ALS cycle
        if cb["n_frames"] < 1:
            raise ValueError(f"no cycle edges in {fc_name!r}")
        edges = cb["edges"]
        inject_cycle = None
        inject_off_ms = None
        # '<=' so a boundary edge belongs to the cycle it STARTS: the deterministic
        # fixed-frame injection lands at +0.0 ms on a cycle boundary, so it must
        # read as cycle #(N+1) +0.0, matching als_inject_align and the gate-2 number.
        k = int(np.sum(edges <= idx))
        if 0 < k <= edges.size:
            inject_cycle = k
            inject_off_ms = _round((idx - edges[k - 1]) / fs * 1000.0, 1)
        block = {
            "source": "als_branch_a_clock",
            "n_cycles": int(cb["n_frames"]),
            "cycle_rate_hz": _round(cb["rate_hz"], 2),
            "head_pad_s": _round(cb["head_pad_s"], 3),
            "tail_pad_s": _round(cb["tail_pad_s"], 3),
            "inject_cycle": inject_cycle,
            "inject_offset_into_cycle_ms": inject_off_ms,
        }
        if n_cycles_commanded is not None:
            block["n_cycles_commanded"] = int(n_cycles_commanded)
        sidecar["als_datafile_timing"] = block

    return sidecar


def validate(sidecar: dict, schema_path: str) -> None:
    """Raise jsonschema.ValidationError if the sidecar does not conform."""
    import jsonschema  # local import so emission works without jsonschema installed

    with open(schema_path, "r", encoding="utf-8") as fh:
        schema = json.load(fh)
    jsonschema.validate(instance=sidecar, schema=schema)


def main() -> None:
    ap = argparse.ArgumentParser(description="emit a trigger_sync sidecar from a Data Recorder .h5")
    ap.add_argument("h5")
    ap.add_argument("scan_mode", choices=["galvo", "als", "resonant"])
    ap.add_argument("--als-datafile", default=None, help="ALS stem (required for scan_mode=als)")
    ap.add_argument("--n-cycles-commanded", type=int, default=None,
                    help="commanded ALS cycle count (framesPerSlice x numSlices x numVolumes) for cross-check")
    ap.add_argument("--ttl-name", default="Legato130_TTL")
    ap.add_argument("--fc-name", default="frame_clock")
    ap.add_argument("--schema", default=None, help="validate against this trigger_sync.schema.json")
    ap.add_argument("--out", default=None, help="write JSON here (default: stdout)")
    a = ap.parse_args()

    sidecar = build_trigger_sync(
        a.h5, a.scan_mode, als_datafile=a.als_datafile,
        n_cycles_commanded=a.n_cycles_commanded,
        ttl_name=a.ttl_name, fc_name=a.fc_name,
    )
    if a.schema:
        validate(sidecar, a.schema)  # raises on invalid
        print(f"[validate] OK against {os.path.basename(a.schema)}")
    text = json.dumps(sidecar, indent=2, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"[write] {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
