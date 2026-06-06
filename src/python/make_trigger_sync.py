#!/usr/bin/env python3
"""
make_trigger_sync.py — emit a schema-valid trigger_sync sidecar from a Data
Recorder .h5, and (optionally) validate it against trigger_sync.schema.json.

Sibling of make_sidecar.py (als_sidecar). One-way import of the acquisition-repo
loader: reads the .h5 with datarecorder_loader, derives injection t0 (the recorded
TTL edge = analysis time-zero) and, for galvo/resonant, the frame timebase from
frame_clock; for ALS there is no frame_clock, so anchor = als_datafile_timing.

scan_mode -> anchor (enforced by the schema's allOf, mirrored here):
    galvo / resonant : anchor='frame_clock'        + frame_timebase (required)
    als              : anchor='als_datafile_timing' + als_datafile  (required)

Usage:
    python make_trigger_sync.py <h5> galvo  [--schema trigger_sync.schema.json] [--out s.json]
    python make_trigger_sync.py <h5> als    --als-datafile <stem> [--schema ...] [--out ...]
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np

import datarecorder_loader as DR

SCHEMA_VERSION = "0.1.0"


def _round(x, n):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


def build_trigger_sync(
    h5_path: str,
    scan_mode: str,
    als_datafile: str | None = None,
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
        "datarecorder_file": os.path.basename(h5_path),
        "als_datafile": als_datafile if scan_mode == "als" else None,
        "signals": {
            "injector_ttl": ttl_name,
            "frame_clock": (fc_name if (scan_mode != "als" and fc_name in data["signals"]) else None),
        },
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

    # --- frame timebase (galvo/resonant only) --------------------------------
    if scan_mode != "als":
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
        k = int(np.sum(edges < idx))
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
    ap.add_argument("--ttl-name", default="Legato130_TTL")
    ap.add_argument("--fc-name", default="frame_clock")
    ap.add_argument("--schema", default=None, help="validate against this trigger_sync.schema.json")
    ap.add_argument("--out", default=None, help="write JSON here (default: stdout)")
    a = ap.parse_args()

    sidecar = build_trigger_sync(
        a.h5, a.scan_mode, als_datafile=a.als_datafile,
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
