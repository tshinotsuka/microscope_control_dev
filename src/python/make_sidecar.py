"""
make_sidecar.py — Build a per-acquisition JSON sidecar from a ScanImage ALS
.meta.txt (and the sibling .pmt.dat for the cycle count).

    python make_sidecar.py <stem-or-meta.txt> [-o out.json]

The sidecar holds scan_mode/acq and acquisition geometry that are intentionally
kept OUT of the filename. Validate with als_sidecar.schema.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re

import als_loader as al

_FNAME_RE = re.compile(r"^(?:(?P<date>\d{8})_)?(?P<entities>.+?)(?:_(?P<counter>\d{4,6}))?$")


def parse_filename(stem_basename: str) -> dict:
    """sub-ref_ses-01_cond-cagegfpfixed_run-01_00001 ->
       {date, entities:{sub,ses,cond,run}, counter}."""
    m = _FNAME_RE.match(stem_basename)
    date = m.group("date")
    counter = m.group("counter") or ""
    entities: dict[str, str] = {}
    for tok in m.group("entities").split("_"):
        if "-" in tok:
            k, v = tok.split("-", 1)
            entities[k] = v
    return {"date": date, "entities": entities, "counter": counter}


def _infer_acq(scan_mode: str, roi_group: dict) -> str:
    rois = _rois(roi_group)
    line_like = [r for r in rois if "line" in (r.get("function") or "")]
    if not line_like:
        return "raster"
    return "als-multiline" if len(rois) > 1 else "als-line"


def _rois(roi_group: dict) -> list[dict]:
    return al.scanfields(roi_group)


def build_sidecar(stem: str) -> dict:
    if stem.endswith(".meta.txt"):
        stem = stem[: -len(".meta.txt")]
    si, roi = al.parse_meta(stem + ".meta.txt")
    info = al.acq_info(si)
    fn = parse_filename(os.path.basename(stem))

    pmt_path = stem + ".pmt.dat"
    n_cycles = None
    if os.path.exists(pmt_path):
        per_cycle = info.pmt_samples_per_cycle * len(info.pmt_channels) * al.PMT_DTYPE.itemsize
        if per_cycle:
            n_cycles = os.path.getsize(pmt_path) // per_cycle

    rois = _rois(roi)
    rg = roi.get("RoiGroups", {}).get("imagingRoiGroup", {})

    sidecar = {
        "identification": {
            "date": fn["date"],
            "entities": fn["entities"],
            "counter": fn["counter"],
        },
        "acq": {
            "scan_mode": info.scan_mode,
            "acq": _infer_acq(info.scan_mode, roi),
            "scanner_type": info.scanner_type,
            "premium": si.get("PREMIUM"),
            "scanimage_version": f"{si.get('VERSION_MAJOR')}.{si.get('VERSION_MINOR')}.{si.get('VERSION_UPDATE')}",
            "version_commit": si.get("VERSION_COMMIT"),
        },
        "timing": {
            "pmt_sample_rate_hz": info.pmt_sample_rate,
            "pmt_samples_per_cycle": info.pmt_samples_per_cycle,
            "fdbk_sample_rate_hz": info.fdbk_sample_rate or None,
            "fdbk_samples_per_cycle": info.fdbk_samples_per_cycle or None,
            "n_cycles": int(n_cycles) if n_cycles is not None else None,
            "cycle_duration_s": info.cycle_duration_s,
            "cycle_rate_hz": info.cycle_rate_hz,
        },
        "channels": {
            "saved": info.pmt_channels,
            "dtype": str(si.get("hScan2D.channelsDataType", "int16")),
            "adc_resolution_bits": si.get("hScan2D.channelsAdcResolution"),
            "input_ranges_v": info.channel_input_ranges,
            "offsets": info.channel_offsets,
            "subtract_offsets": info.channels_subtract_offsets,
        },
        "feedback": {
            "recorded": info.record_feedback,
            "n_channels": info.fdbk_channels or None,
            "dtype": "single" if info.record_feedback else None,
        },
        "path": {
            "roi_group_name": rg.get("name"),
            "rois": rois,
        },
        "files": {
            "stem": os.path.basename(stem),
            "meta": os.path.basename(stem) + ".meta.txt",
            "pmt": os.path.basename(stem) + ".pmt.dat" if os.path.exists(pmt_path) else None,
            "scnnr": os.path.basename(stem) + ".scnnr.dat" if os.path.exists(stem + ".scnnr.dat") else None,
        },
        "provenance": {
            "machine_data_file": None,  # not in the line-scan meta; fill from layout if needed
            "acq_state": si.get("acqState"),
            "generated_by": "make_sidecar.py",
        },
    }
    return sidecar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stem", help="path to <stem> or <stem>.meta.txt")
    ap.add_argument("-o", "--out", help="output .json (default: <stem>.json)")
    args = ap.parse_args()
    sc = build_sidecar(args.stem)
    stem = args.stem[:-len(".meta.txt")] if args.stem.endswith(".meta.txt") else args.stem
    out = args.out or (stem + ".json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(sc, fh, indent=2, ensure_ascii=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
