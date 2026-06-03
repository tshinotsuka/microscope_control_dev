"""
make_behavior_sidecar.py — Build a per-acquisition JSON sidecar from a
BehaviorAcquisition.m session (behavior.h5 + config.json).

    python make_behavior_sidecar.py <session_dir> [--stem STEM]
        [--injector-channel injector] [--frame-clock-channel frame_clock]
        [--threshold 2.5] [--min-gap 50] [-o out.json] [--csv]

The sidecar carries the BIDS entities (shared stem with the ScanImage GRAB),
channel roles, the clock-domain reconciliation, and derived trigger/injection
events (trigger_sync). Mirrors make_sidecar.py for ALS.

The injector emits a TTL on/off; it is recorded as a behavior channel (like
frame_clock), so injection on/off lands on the SAME clock as all behavior data.
This script derives the on/off intervals by threshold crossing (the same logic
as analysis_postprocess.detect_events) and records the detection params so the
event table is reproducible from the raw channel.

Validate with behavior_sidecar_schema.json.   Deps: numpy, h5py.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re

import numpy as np
import h5py

# shared GRAB-stem grammar (mirrors make_sidecar.parse_filename)
_FNAME_RE = re.compile(r"^(?:(?P<date>\d{8})_)?(?P<entities>.+?)(?:_(?P<counter>\d{4,6}))?$")

TTL_CHANNELS_DEFAULT = ("frame_clock", "injector")


def parse_filename(stem_basename: str) -> dict:
    """sub-ref_ses-01_cond-..._run-01_00001 -> {date, entities:{...}, counter}."""
    m = _FNAME_RE.match(stem_basename)
    date = m.group("date")
    counter = m.group("counter") or ""
    entities: dict[str, str] = {}
    for tok in m.group("entities").split("_"):
        if "-" in tok:
            k, v = tok.split("-", 1)
            entities[k] = v
    return {"date": date, "entities": entities, "counter": counter}


def _attr_str(ds, k):
    v = ds.attrs.get(k)
    if isinstance(v, bytes):
        return v.decode(errors="replace")
    return str(v) if v is not None else None


def _attr_num(ds, k):
    v = ds.attrs.get(k)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _intervals(x: np.ndarray, thresh: float, min_gap: int):
    """Rising->falling intervals above threshold, with min_gap debounce on rises.
    Returns list of (on_sample, off_sample|None)."""
    above = (x > thresh).astype(np.int8)
    d = np.diff(above, prepend=above[0])
    rises = np.flatnonzero(d == 1)
    falls = np.flatnonzero(d == -1)
    if len(rises):
        keep = np.empty(len(rises), bool)
        keep[0] = True
        keep[1:] = np.diff(rises) >= min_gap
        rises = rises[keep]
    out, fi = [], 0
    for r in rises:
        while fi < len(falls) and falls[fi] <= r:
            fi += 1
        off = int(falls[fi]) if fi < len(falls) else None
        out.append((int(r), off))
    return out


def build_sidecar(session_dir: str, stem: str | None = None,
                  injector_channel: str = "injector",
                  frame_clock_channel: str = "frame_clock",
                  threshold: float = 2.5, min_gap: int = 50,
                  ttl_channels=TTL_CHANNELS_DEFAULT) -> dict:
    session_dir = os.path.abspath(session_dir)
    h5_path = os.path.join(session_dir, "behavior.h5")
    cfg_path = os.path.join(session_dir, "config.json")
    cfg = json.load(open(cfg_path)) if os.path.exists(cfg_path) else {}
    cfg_chan = {c.get("name"): c for c in cfg.get("channels", [])}

    with h5py.File(h5_path, "r") as f:
        fs = float(f.attrs.get("sample_rate", cfg.get("sample_rate", 0)) or 0)
        session_name = _root_attr_str(f, "session_name") or str(cfg.get("session_name", ""))
        start_time = _root_attr_str(f, "start_time") or cfg.get("start_time")
        chan_names = list(f["analog"].keys()) if "analog" in f else []
        n_samples = int(f["time"].shape[0]) if "time" in f else None
        has_frame_log = "frame_log" in f

        chan_attr = {}
        for name in chan_names:
            ds = f["analog"][name]
            chan_attr[name] = {
                "physical_channel": _attr_str(ds, "physical_channel"),
                "min_val": _attr_num(ds, "min_val"),
                "max_val": _attr_num(ds, "max_val"),
            }

        events, sources = {}, []
        if injector_channel in chan_names:
            x = f["analog"][injector_channel][:].astype(np.float64)
            ev = []
            for on, off in _intervals(x, threshold, min_gap):
                rec = {"on_sample": on, "on_s": on / fs if fs else None,
                       "off_sample": off,
                       "off_s": (off / fs) if (off is not None and fs) else None,
                       "duration_s": ((off - on) / fs) if (off is not None and fs) else None}
                ev.append(rec)
            events["injection"] = ev
            sources.append({"name": "injection", "channel": injector_channel,
                            "threshold_v": threshold, "direction": "rising",
                            "min_gap_samples": min_gap, "encoding": "interval"})

    stem = stem or session_name or os.path.basename(session_dir)
    fn = parse_filename(os.path.basename(stem))

    device = None
    for name in chan_names:
        pc = chan_attr[name]["physical_channel"] or cfg_chan.get(name, {}).get("physical")
        if pc and "/" in pc:
            device = pc.split("/")[0]
            break

    channels = []
    for name in chan_names:
        lo, hi = chan_attr[name]["min_val"], chan_attr[name]["max_val"]
        rng = [lo, hi] if (lo is not None and hi is not None) else None
        channels.append({
            "name": name,
            "physical_channel": chan_attr[name]["physical_channel"] or cfg_chan.get(name, {}).get("physical"),
            "role": name,  # CONTRACT: refine against metadata_schema.md channels[].name
            "kind": "ttl" if name in ttl_channels else "signal",
            "input_range_v": rng,
        })

    return {
        "identification": {"date": fn["date"], "entities": fn["entities"], "counter": fn["counter"]},
        "acq": {"acq": "behavior", "description": None},
        "timing": {
            "sample_rate_hz": fs,
            "n_samples": n_samples,
            "duration_s": (n_samples / fs) if (n_samples and fs) else None,
            "start_time": start_time if isinstance(start_time, str) else None,
        },
        "clock": {
            "device": device,
            "device_is_vdaq": False,   # behavior AI is on a separate NI board, NOT the vDAQ
            "frame_alignment": "frame_clock_ttl",
            "frame_clock_channel": frame_clock_channel if frame_clock_channel in chan_names else None,
            "frame_log_role": "cross_check" if has_frame_log else "absent",
            "note": ("ScanImage frames are aligned via the recorded frame_clock TTL "
                     "(same DAQ clock as behavior). frame_log/sample_index is a coarse, "
                     "chunk-quantized cross-check only."),
        },
        "channels": channels,
        "triggers": {"sources": sources, "events": events},
        "links": {"scanimage_stems": [os.path.basename(stem)] if stem else []},
        "files": {
            "stem": os.path.basename(stem),
            "behavior_h5": "behavior.h5" if os.path.exists(h5_path) else None,
            "config_json": "config.json" if os.path.exists(cfg_path) else None,
            "injection_csv": None,
        },
        "provenance": {"generated_by": "make_behavior_sidecar.py", "session_name": session_name},
    }


def _root_attr_str(f, k):
    v = f.attrs.get(k)
    if isinstance(v, bytes):
        return v.decode(errors="replace")
    return str(v) if v is not None else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session_dir", help="dir containing behavior.h5 (+ config.json)")
    ap.add_argument("--stem", default=None, help="ScanImage GRAB stem this behavior accompanies")
    ap.add_argument("--injector-channel", default="injector")
    ap.add_argument("--frame-clock-channel", default="frame_clock")
    ap.add_argument("--threshold", type=float, default=2.5)
    ap.add_argument("--min-gap", type=int, default=50)
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--csv", action="store_true", help="also write injection.csv")
    args = ap.parse_args()

    sc = build_sidecar(args.session_dir, stem=args.stem,
                       injector_channel=args.injector_channel,
                       frame_clock_channel=args.frame_clock_channel,
                       threshold=args.threshold, min_gap=args.min_gap)

    if args.csv and sc["triggers"]["events"].get("injection"):
        csv_path = os.path.join(os.path.abspath(args.session_dir), "injection.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["on_sample", "on_s", "off_sample", "off_s", "duration_s"])
            w.writeheader()
            w.writerows(sc["triggers"]["events"]["injection"])
        sc["files"]["injection_csv"] = "injection.csv"
        print(f"wrote {csv_path}")

    out = args.out or os.path.join(os.path.abspath(args.session_dir), "behavior_sidecar.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(sc, fh, indent=2, ensure_ascii=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
