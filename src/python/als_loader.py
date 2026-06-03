"""
als_loader.py — Reader for ScanImage Arbitrary Line Scanning (ALS) output.

A single GRAB produces 3 files sharing one stem:
    <stem>.meta.txt   ScanImage params (dot-syntax) + scan-path (JSON)
    <stem>.pmt.dat    fluorescence, int16, channel-interleaved
    <stem>.scnnr.dat  scanner XY feedback, float32 (only if feedback ON)

On-disk sample order for both .dat files is channel-fastest:
    [c0 s0, c1 s0, ..., cN s0, c0 s1, ...]  per frame/cycle, frames concatenated.
So a C-order reshape to (n_cycles, samples_per_cycle, n_channels) yields
[cycle, sample, channel].

Verified against SI Premium 2026.0.0 line-scan output. The official MATLAB
equivalent is scanimage.util.readLineScanDataFiles(stem).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

PMT_DTYPE = np.dtype("<i2")   # int16, little-endian
FDBK_DTYPE = np.dtype("<f4")  # single, little-endian


# --------------------------------------------------------------------------- #
# meta.txt parsing
# --------------------------------------------------------------------------- #
def _parse_matrix(s: str):
    """Parse a MATLAB matrix literal '[a b;c d]' into a nested list (or scalar)."""
    inner = s.strip()[1:-1].strip()
    if inner == "":
        return []
    rows = [r for r in inner.split(";")]
    parsed = []
    for r in rows:
        toks = r.replace(",", " ").split()
        parsed.append([_parse_scalar(t) for t in toks])
    if len(parsed) == 1:
        return parsed[0] if len(parsed[0]) != 1 else parsed[0][0]
    return parsed


def _parse_scalar(t: str):
    t = t.strip()
    low = t.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("inf", "+inf"):
        return float("inf")
    if low == "-inf":
        return float("-inf")
    if low == "nan":
        return float("nan")
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        return t


def _parse_value(s: str):
    """Best-effort conversion of a dot-syntax RHS to a Python object.

    Never raises: unknown forms fall back to the raw stripped string.
    """
    s = s.strip()
    if s == "" or s == "[]":
        return None
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1]
    if s in ("true", "false"):
        return s == "true"
    if s.startswith("zeros(") or s.startswith("ones("):
        return []
    if s.startswith("{") and s.endswith("}"):
        # cell array: pull out bracketed groups, else keep raw
        groups = re.findall(r"\[[^\]]*\]", s)
        if groups:
            return [_parse_matrix(g) for g in groups]
        return s  # opaque cell -> raw
    if s.startswith("[") and s.endswith("]"):
        try:
            return _parse_matrix(s)
        except Exception:
            return s
    val = _parse_scalar(s)
    return val


def parse_meta(meta_path: str) -> tuple[dict, dict]:
    """Return (si_params_flat, roi_group).

    si_params_flat: dict keyed by dotted path WITHOUT the leading 'SI.'
                    e.g. si['hScan2D.sampleRate'] == 2500000
    roi_group:      parsed JSON scan-path block (or {} if absent)
    """
    with open(meta_path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()

    si: dict[str, Any] = {}
    json_start = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("{"):
            json_start = i
            break
        if "=" not in line:
            continue
        key, _, rhs = line.partition("=")
        key = key.strip()
        if not key.startswith("SI."):
            continue
        si[key[3:]] = _parse_value(rhs)

    roi_group: dict = {}
    if json_start is not None:
        blob = "\n".join(lines[json_start:]).strip()
        try:
            roi_group = json.loads(blob)
        except json.JSONDecodeError:
            roi_group = {}
    return si, roi_group


# --------------------------------------------------------------------------- #
# acquisition info
# --------------------------------------------------------------------------- #
@dataclass
class AcqInfo:
    pmt_channels: list[int]
    pmt_samples_per_cycle: int
    pmt_sample_rate: float
    fdbk_channels: int
    fdbk_samples_per_cycle: int
    fdbk_sample_rate: float
    record_feedback: bool
    channel_offsets: list[int] = field(default_factory=list)
    channel_input_ranges: list = field(default_factory=list)
    channels_subtract_offsets: list = field(default_factory=list)
    scanner_type: str = ""
    scan_mode: str = ""

    @property
    def cycle_duration_s(self) -> float:
        return self.pmt_samples_per_cycle / self.pmt_sample_rate

    @property
    def cycle_rate_hz(self) -> float:
        return self.pmt_sample_rate / self.pmt_samples_per_cycle


def _as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def acq_info(si: dict) -> AcqInfo:
    return AcqInfo(
        pmt_channels=_as_list(si.get("hChannels.channelSave")),
        pmt_samples_per_cycle=int(si["hScan2D.lineScanSamplesPerFrame"]),
        pmt_sample_rate=float(si["hScan2D.sampleRate"]),
        fdbk_channels=int(si.get("hScan2D.lineScanNumFdbkChannels", 0) or 0),
        fdbk_samples_per_cycle=int(si.get("hScan2D.lineScanFdbkSamplesPerFrame", 0) or 0),
        fdbk_sample_rate=float(si.get("hScan2D.sampleRateFdbk", 0) or 0),
        record_feedback=bool(si.get("hScan2D.recordScannerFeedback", False)),
        channel_offsets=_as_list(si.get("hScan2D.channelOffsets")),
        channel_input_ranges=_as_list(si.get("hScan2D.channelsInputRanges")),
        channels_subtract_offsets=_as_list(si.get("hScan2D.channelsSubtractOffsets")),
        scanner_type=str(si.get("hScan2D.scannerType", "")),
        scan_mode=str(si.get("hScan2D.scanMode", "")),
    )


# --------------------------------------------------------------------------- #
# binary readers
# --------------------------------------------------------------------------- #
def _read_binary(path: str, dtype, samples_per_cycle: int, n_channels: int) -> np.ndarray:
    flat = np.fromfile(path, dtype=dtype)
    per_cycle = samples_per_cycle * n_channels
    if per_cycle == 0:
        raise ValueError("samples_per_cycle * n_channels == 0")
    n_cycles, rem = divmod(flat.size, per_cycle)
    if rem != 0:
        raise ValueError(
            f"{os.path.basename(path)}: {flat.size} samples not divisible by "
            f"{per_cycle} (={samples_per_cycle}x{n_channels}); meta/file mismatch"
        )
    return flat.reshape(n_cycles, samples_per_cycle, n_channels)


def load_pmt(path: str, info: AcqInfo) -> np.ndarray:
    """-> int16 array [cycle, sample, channel]."""
    return _read_binary(path, PMT_DTYPE, info.pmt_samples_per_cycle, len(info.pmt_channels))


def load_scnnr(path: str, info: AcqInfo) -> np.ndarray:
    """-> float32 array [cycle, sample, channel]; channels = (X, Y[, Z])."""
    return _read_binary(path, FDBK_DTYPE, info.fdbk_samples_per_cycle, info.fdbk_channels)


def pmt_to_volts(pmt: np.ndarray, info: AcqInfo, subtract_offset: bool = False) -> np.ndarray:
    """Convert raw int16 counts to volts using per-channel input range.

    NOTE: whether on-disk data is pre/post offset is not 100% documented;
    leave subtract_offset=False until cross-checked vs readLineScanDataFiles.
    """
    out = pmt.astype(np.float64)
    nch = pmt.shape[-1]
    if subtract_offset and len(info.channel_offsets) >= nch:
        out = out - np.asarray(info.channel_offsets[:nch], dtype=np.float64)
    for c in range(nch):
        rng = info.channel_input_ranges[c] if c < len(info.channel_input_ranges) else [-1, 1]
        lo, hi = float(rng[0]), float(rng[1])
        half, mid = (hi - lo) / 2.0, (hi + lo) / 2.0
        out[..., c] = out[..., c] / 32768.0 * half + mid
    return out


# --------------------------------------------------------------------------- #
# high-level
# --------------------------------------------------------------------------- #
@dataclass
class LineScan:
    stem: str
    si: dict
    roi_group: dict
    info: AcqInfo
    pmt: np.ndarray | None = None
    scnnr: np.ndarray | None = None


def load(stem: str, read_data: bool = True) -> LineScan:
    """Load an ALS acquisition. `stem` is the path WITHOUT extension,
    e.g. '/data/.../20260529_sub-ref_ses-01_cond-cagegfpfixed_run-01_00001'.
    """
    if stem.endswith(".meta.txt"):
        stem = stem[: -len(".meta.txt")]
    si, roi = parse_meta(stem + ".meta.txt")
    info = acq_info(si)
    ls = LineScan(stem=stem, si=si, roi_group=roi, info=info)
    if read_data:
        pmt_path = stem + ".pmt.dat"
        if os.path.exists(pmt_path):
            ls.pmt = load_pmt(pmt_path, info)
        scn_path = stem + ".scnnr.dat"
        if info.record_feedback and os.path.exists(scn_path):
            ls.scnnr = load_scnnr(scn_path, info)
    return ls


def scanfields(roi_group: dict) -> list[dict]:
    """Flatten imagingRoiGroup -> list of scanfields in path order."""
    rg = roi_group.get("RoiGroups", {}).get("imagingRoiGroup", {})
    raw = rg.get("rois")
    if isinstance(raw, dict):
        raw = [raw]
    elif not isinstance(raw, list):
        return []
    out = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        sf = r.get("scanfields")
        if isinstance(sf, list):
            sf = sf[0] if sf else {}
        sf = sf or {}
        out.append({
            "name": r.get("name"),
            "function": sf.get("stimulusFunction"),
            "center_xy": sf.get("centerXY"),
            "size_xy": sf.get("sizeXY"),
            "rotation_deg": sf.get("rotationDegrees"),
            "zs": r.get("zs"),
            "duration_s": sf.get("duration"),
            "repetitions": sf.get("repetitions"),
        })
    return out


def segment_samples(si: dict, roi_group: dict) -> dict:
    """Per-scanfield sample windows within one cycle, for both PMT and feedback.

    Returns {'segments': [...], 'pmt_leftover': int, 'fdbk_leftover': int}.
    Each segment maps a path element (a line / pause / park) to the sample
    index range [start, stop) it occupies in each cycle. `leftover` > 0 means
    the cycle contains time NOT covered by listed scanfields (implicit
    transitions / auto-inserted pauses) — the analysis must decide whether to
    trim or keep it. This is the key primitive for splitting multi-line data.
    """
    info = acq_info(si)
    sfs = scanfields(roi_group)
    segs, pmt_cur, fdbk_cur = [], 0, 0
    for s in sfs:
        dur = float(s.get("duration_s") or 0.0)
        n_pmt = int(round(dur * info.pmt_sample_rate))
        n_fdbk = int(round(dur * info.fdbk_sample_rate)) if info.fdbk_sample_rate else 0
        segs.append({
            "name": s["name"], "function": s["function"], "duration_s": dur,
            "pmt": [pmt_cur, pmt_cur + n_pmt],
            "fdbk": [fdbk_cur, fdbk_cur + n_fdbk],
        })
        pmt_cur += n_pmt
        fdbk_cur += n_fdbk
    return {
        "segments": segs,
        "pmt_leftover": info.pmt_samples_per_cycle - pmt_cur,
        "fdbk_leftover": (info.fdbk_samples_per_cycle - fdbk_cur) if info.fdbk_samples_per_cycle else 0,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: python als_loader.py <stem-or-meta.txt>")
        sys.exit(1)
    ls = load(sys.argv[1])
    i = ls.info
    print(f"scanner       : {i.scanner_type}  mode={i.scan_mode}")
    print(f"pmt           : {len(i.pmt_channels)} ch x {i.pmt_samples_per_cycle} samp "
          f"@ {i.pmt_sample_rate/1e6:g} MHz")
    print(f"feedback      : {i.fdbk_channels} ch x {i.fdbk_samples_per_cycle} samp "
          f"@ {i.fdbk_sample_rate/1e3:g} kHz  (recorded={i.record_feedback})")
    print(f"cycle         : {i.cycle_duration_s*1e3:g} ms  -> {i.cycle_rate_hz:g} Hz")
    if ls.pmt is not None:
        print(f"pmt array     : {ls.pmt.shape}  {ls.pmt.dtype}  [cycle,sample,channel]")
    if ls.scnnr is not None:
        print(f"scnnr array   : {ls.scnnr.shape}  {ls.scnnr.dtype}  [cycle,sample,XY]")
    rg = ls.roi_group.get("RoiGroups", {}).get("imagingRoiGroup", {})
    print(f"roi group     : {rg.get('name','?')}")
