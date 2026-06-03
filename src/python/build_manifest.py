"""
build_manifest.py — Inventory every ScanImage ALS acquisition in a folder.

    python build_manifest.py <data_dir> [-o manifest.json] [--csv manifest.csv] [--sidecars]

For each *.meta.txt it derives the sidecar fields, the per-line sample segments,
and the total acquisition duration, and writes:
  - manifest.json : one record per acquisition (machine-readable handoff)
  - manifest.csv  : flat table (human scan)               [optional]
  - <stem>.json   : per-acquisition sidecar                [with --sidecars]

This is the artifact the analysis chat loads to know what data exists.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os

import als_loader as al
import make_sidecar as ms


def record_for(meta_path: str) -> dict:
    stem = meta_path[: -len(".meta.txt")]
    si, roi = al.parse_meta(meta_path)
    sc = ms.build_sidecar(stem)
    seg = al.segment_samples(si, roi)
    n_cycles = sc["timing"]["n_cycles"]
    cyc = sc["timing"]["cycle_duration_s"]
    n_lines = sum(1 for s in seg["segments"] if "line" in (s["function"] or ""))
    return {
        "stem": os.path.basename(stem),
        "acq": sc["acq"]["acq"],
        "n_lines": n_lines,
        "n_scanfields": len(seg["segments"]),
        "n_cycles": n_cycles,
        "cycle_rate_hz": sc["timing"]["cycle_rate_hz"],
        "duration_s": (n_cycles * cyc) if n_cycles else None,
        "pmt": {
            "channels": sc["channels"]["saved"],
            "samples_per_cycle": sc["timing"]["pmt_samples_per_cycle"],
            "sample_rate_hz": sc["timing"]["pmt_sample_rate_hz"],
            "dtype": sc["channels"]["dtype"],
        },
        "feedback": sc["feedback"],
        "segments": seg["segments"],
        "pmt_leftover": seg["pmt_leftover"],
        "fdbk_leftover": seg["fdbk_leftover"],
        "entities": sc["identification"]["entities"],
        "date": sc["identification"]["date"],
        "counter": sc["identification"]["counter"],
        "description": "",  # free field: annotate light/dark, sample, etc.
        "files": sc["files"],
    }


CSV_COLS = ["stem", "acq", "n_lines", "n_cycles", "duration_s", "cycle_rate_hz",
            "pmt_leftover", "fdbk_leftover", "description"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--sidecars", action="store_true", help="also write per-acq <stem>.json")
    args = ap.parse_args()

    metas = sorted(glob.glob(os.path.join(args.data_dir, "*.meta.txt")))
    records = []
    for m in metas:
        try:
            rec = record_for(m)
            records.append(rec)
            if args.sidecars:
                ms_path = m[: -len(".meta.txt")] + ".json"
                with open(ms_path, "w", encoding="utf-8") as fh:
                    json.dump(ms.build_sidecar(m), fh, indent=2, ensure_ascii=False)
        except Exception as e:  # never let one bad file kill the inventory
            records.append({"stem": os.path.basename(m), "error": str(e)})

    manifest = {"n_acquisitions": len(records), "data_dir": os.path.abspath(args.data_dir),
                "acquisitions": records}
    out = args.out or os.path.join(args.data_dir, "manifest.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    print(f"wrote {out}  ({len(records)} acquisitions)")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=CSV_COLS, extrasaction="ignore")
            w.writeheader()
            for r in records:
                w.writerow(r)
        print(f"wrote {args.csv}")


if __name__ == "__main__":
    main()
