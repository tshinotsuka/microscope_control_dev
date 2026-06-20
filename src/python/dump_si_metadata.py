#!/usr/bin/env python3
"""dump_si_metadata.py -- C1 SI-metadata verification for the water-imaging contract.

Opens a ScanImage .tif, pulls the embedded SI.* metadata + RoiGroups + per-frame
ImageDescription, and prints a CHECKLIST of the fields the contract depends on
(value / PASS / MISSING) so you can confirm on REAL hardware that nothing was
renamed or dropped in Premium 2026. Optionally archives a reference snapshot to JSON
(freeze that snapshot into the contract = C1 done).

Field lookup is tolerant: each item is tried as exact dotted key(s) first, then by
substring -- so a renamed key is still FOUND and its NEW name is reported, instead of
silently going MISSING. That surface-of-renames is the whole point of the check.

env: mcd-quicklook (needs tifffile). stdlib only otherwise.

usage:
  python dump_si_metadata.py RUN_00001.tif
  python dump_si_metadata.py RUN_00001.tif --full
  python dump_si_metadata.py RUN_00001.tif --als-stem /path/RUN_00002 --json c1_ref.json
"""
import argparse
import ast
import glob
import json
import math
import os
import sys

import tifffile


# ---------------------------------------------------------------- parsing helpers
def _coerce(s):
    """Best-effort scalar/array parse of a ScanImage value string."""
    if not isinstance(s, str):
        return s
    t = s.strip()
    if t == "":
        return ""
    repl = (t.replace("Inf", 'float("inf")')
             .replace("NaN", 'float("nan")')
             .replace("true", "True").replace("false", "False"))
    try:
        return eval(repl, {"__builtins__": {}}, {"float": float})  # noqa: S307 (sandboxed)
    except Exception:
        try:
            return ast.literal_eval(t)
        except Exception:
            return t


def parse_description(text):
    """Per-frame ImageDescription 'key = value' lines -> dict."""
    out = {}
    if not text:
        return out
    for line in str(text).splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = _coerce(v)
    return out


def resolve(fd, exact, subs):
    """Return (matched_key, value, how). exact=list of dotted keys; subs=substrings."""
    for k in exact:
        if k in fd:
            return k, fd[k], "exact"
    low = [s.lower() for s in subs]
    for k in fd:
        kl = k.lower()
        if all(s in kl for s in low):
            return k, fd[k], "substr"
    return None, None, "missing"


def is_inf(v):
    try:
        return math.isinf(float(v))
    except Exception:
        return False


def walk_scanfields(obj):
    """Yield any dict that looks like a scanfield (has sizeXY or pixelResolutionXY)."""
    if isinstance(obj, dict):
        keys = {k.lower() for k in obj.keys()}
        if "sizexy" in keys or "pixelresolutionxy" in keys:
            yield obj
        for v in obj.values():
            yield from walk_scanfields(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from walk_scanfields(v)


def find_in(obj, needle):
    """True if any key (recursively) contains needle (case-insensitive)."""
    needle = needle.lower()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if needle in str(k).lower():
                return True
            if find_in(v, needle):
                return True
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            if find_in(v, needle):
                return True
    return False


def g(d, *names):
    """case-insensitive get on a scanfield dict."""
    low = {k.lower(): v for k, v in d.items()}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return None


# ---------------------------------------------------------------- checklist spec
# (label, exact dotted candidates, substrings, note)
CHECKS = [
    ("ScanImage version",  ["SI.VERSION_MAJOR"],                ["version_major"], "record producing version"),
    ("channelSave",        ["SI.hChannels.channelSave"],        ["channelsave"],   "expect [1,2,3,4]; SRS=Ch3"),
    ("objectiveResolution",["SI.objectiveResolution"],          ["objectiveresolution"], "um per scan-unit (calib)"),
    ("scanFrameRate",      ["SI.hRoiManager.scanFrameRate"],    ["scanframerate"], "raster ~1 Hz"),
    ("linePeriod",         ["SI.hRoiManager.linePeriod"],       ["lineperiod"],    ""),
    ("linesPerFrame",      ["SI.hRoiManager.linesPerFrame"],    ["linesperframe"], ""),
    ("pixelsPerLine",      ["SI.hRoiManager.pixelsPerLine",
                            "SI.hScan2D.pixelsPerLine"],         ["pixelsperline"], ""),
    ("framesPerSlice",     ["SI.hStackManager.framesPerSlice"], ["framesperslice"],"expect Inf (Gate1)"),
    ("scannerToRefTransform", ["SI.hScan2D.scannerToRefTransform"], ["toreftransform"], "ref-space registration"),
]


def derive_um_per_px(size_xy, pix_xy, obj_res):
    """um/px cross-check = (size * objectiveResolution) / pixels, per axis. None if not derivable."""
    try:
        sx, sy = float(size_xy[0]), float(size_xy[1])
        px, py = float(pix_xy[0]), float(pix_xy[1])
        o = float(obj_res[0]) if isinstance(obj_res, (list, tuple)) else float(obj_res)
        return [sx * o / px, sy * o / py]
    except Exception:
        return None


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="C1 SI-metadata dump / verify")
    ap.add_argument("tif", help="ScanImage .tif (e.g. the 1Hz raster RUN_00001.tif)")
    ap.add_argument("--als-stem", default=None,
                    help="ALS run stem; checks ALS datafile(s) exist on disk next to it")
    ap.add_argument("--full", action="store_true",
                    help="also dump the entire FrameData + RoiGroups")
    ap.add_argument("--json", dest="json_out", default=None,
                    help="write reference snapshot to this JSON (the C1 freeze artifact)")
    args = ap.parse_args()

    if not os.path.isfile(args.tif):
        sys.exit(f"ERROR: not found: {args.tif}")

    with tifffile.TiffFile(args.tif) as tf:
        try:
            md = tf.scanimage_metadata or {}
        except Exception as e:
            md = {}
            print(f"[warn] scanimage_metadata failed: {e}")
        fd = (md.get("FrameData") or {}) if isinstance(md, dict) else {}
        roi = (md.get("RoiGroups") or {}) if isinstance(md, dict) else {}
        n_pages = len(tf.pages)
        try:
            shape, dtype = tf.pages[0].shape, str(tf.pages[0].dtype)
        except Exception:
            shape, dtype = None, None
        desc0 = parse_description(tf.pages[0].description) if n_pages else {}
        descN = parse_description(tf.pages[-1].description) if n_pages else {}

    if not fd:
        print("=" * 64)
        print("NO ScanImage metadata found -- not an SI tif, or tifffile too old.")
        print("=" * 64)
        sys.exit(2)

    bar = "=" * 64
    print(bar)
    print(f"FILE   {os.path.basename(args.tif)}")
    print(f"pages  {n_pages}   page0 shape {shape} dtype {dtype}")

    # channels / frames
    _, chsave, _ = resolve(fd, ["SI.hChannels.channelSave"], ["channelsave"])
    nch = len(chsave) if isinstance(chsave, (list, tuple)) else (1 if chsave is not None else None)
    if nch:
        print(f"channelSave {chsave}  -> {nch} ch saved, ~{n_pages // nch} frames (interleaved)")
    print(bar)

    # ---- checklist ----
    snapshot = {"file": os.path.basename(args.tif), "n_pages": n_pages,
                "page0_shape": list(shape) if shape else None, "dtype": dtype,
                "checks": {}, "imaging_scanfields": [], "timing": {},
                "als": {}, "raster_tif": os.path.abspath(args.tif)}
    print("C1 CHECKLIST (label : value  [how]  -- note)")
    print("-" * 64)
    for label, exact, subs, note in CHECKS:
        key, val, how = resolve(fd, exact, subs)
        if how == "missing":
            print(f"  MISSING  {label:<22} -- {note}")
            snapshot["checks"][label] = {"status": "MISSING", "note": note}
            continue
        disp = val
        extra = ""
        if label == "framesPerSlice":
            extra = "  [Inf OK]" if is_inf(val) else "  [!! not Inf]"
        tag = "" if how == "exact" else f"  [renamed->{key}]"
        print(f"  {label:<22} = {disp}{extra}{tag}")
        snapshot["checks"][label] = {"status": "OK", "key": key, "value": val,
                                     "how": how, "note": note}
    print("-" * 64)

    # ---- per-frame timing (from page descriptions) ----
    ft0 = desc0.get("frameTimestamps_sec")
    ftN = descN.get("frameTimestamps_sec")
    at0 = desc0.get("acqTriggerTimestamps_sec")
    fn0, fnN = desc0.get("frameNumbers"), descN.get("frameNumbers")
    print("TIMING (per-frame ImageDescription)")
    if ft0 is None:
        print("  MISSING  frameTimestamps_sec")
    else:
        rate = None
        try:
            if ftN is not None and ftN != ft0 and fnN and fn0:
                rate = (float(fnN) - float(fn0)) / (float(ftN) - float(ft0))
        except Exception:
            pass
        print(f"  frameTimestamps_sec   first={ft0}  last={ftN}"
              + (f"  (~{rate:.3f} frame/s)" if rate else ""))
    print(f"  acqTriggerTimestamps_sec  first={at0}"
          if at0 is not None else "  MISSING  acqTriggerTimestamps_sec")
    snapshot["timing"] = {"frameTimestamps_sec": [ft0, ftN],
                          "acqTriggerTimestamps_sec": at0,
                          "frameNumbers": [fn0, fnN]}
    print("-" * 64)

    # ---- imaging scanfields + pixel-size cross-check ----
    _, objres, _ = resolve(fd, ["SI.objectiveResolution"], ["objectiveresolution"])
    sfs = list(walk_scanfields(roi))
    print(f"RoiGroups scanfields found: {len(sfs)}")
    for i, sf in enumerate(sfs):
        size = g(sf, "sizeXY")
        pix = g(sf, "pixelResolutionXY")
        cen = g(sf, "centerXY")
        rot = g(sf, "rotationDegrees", "rotation")
        upx = derive_um_per_px(size, pix, objres) if (size and pix and objres is not None) else None
        line = f"  [{i}] size={size} pix={pix} center={cen} rot={rot}"
        if upx:
            line += f"  -> ~{upx[0]:.3f} um/px (cross-check; raster expect ~0.909)"
        print(line)
        snapshot["imaging_scanfields"].append(
            {"sizeXY": size, "pixelResolutionXY": pix, "centerXY": cen,
             "rotation": rot, "um_per_px_xcheck": upx})
    als_in_roi = find_in(roi, "stimulus")
    print(f"  StimulusField (ALS line) present in RoiGroups: {als_in_roi}")
    snapshot["als"]["stimulusfield_in_roigroups"] = als_in_roi
    print("-" * 64)

    # ---- ALS datafile presence on disk ----
    if args.als_stem:
        cands = sorted(set(glob.glob(args.als_stem + "*")))
        cands = [c for c in cands if not c.lower().endswith((".tif", ".tiff"))]
        print(f"ALS datafiles near stem ({len(cands)}):")
        for c in cands:
            print(f"  {os.path.basename(c):<40} {os.path.getsize(c):>12,} B")
        snapshot["als"]["stem"] = os.path.abspath(args.als_stem)
        snapshot["als"]["datafiles"] = [
            {"name": os.path.basename(c), "bytes": os.path.getsize(c)} for c in cands]
        print("-" * 64)

    # ---- full dump ----
    if args.full:
        print("FULL FrameData (sorted):")
        for k in sorted(fd):
            print(f"  {k} = {fd[k]}")
        print("-" * 64)
        print("FULL RoiGroups:")
        print(json.dumps(roi, indent=2, default=str))
        print("-" * 64)
        print("page0 description:")
        for k, v in desc0.items():
            print(f"  {k} = {v}")
        print(bar)
        snapshot["framedata_full"] = {k: _jsonable(fd[k]) for k in fd}
        snapshot["roigroups_full"] = roi

    # ---- json snapshot ----
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(snapshot, f, indent=2, default=str)
        print(f"[snapshot] wrote {args.json_out}")

    # ---- one-line verdict ----
    missing = [l for l, c in snapshot["checks"].items() if c.get("status") == "MISSING"]
    if missing:
        print(f"VERDICT: {len(missing)} field(s) MISSING -> {', '.join(missing)}")
    else:
        print("VERDICT: all contract fields present.")


def _jsonable(v):
    try:
        json.dumps(v)
        return v
    except Exception:
        return str(v)


if __name__ == "__main__":
    main()
