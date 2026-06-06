#!/usr/bin/env python3
"""
compare_als_ref.py — P2 cross-check: als_loader.py output vs the MATLAB
scanimage.util.readLineScanDataFiles reference exported to als_ref_*.mat.

Settles the three open ALS-loader questions (roadmap Track-W B / handoff §2):

  1. offset pre/post  — does readLineScanDataFiles return RAW int16 counts, or
     channel-offset-subtracted, or volts? This resolves the `subtract_offset`
     TODO in als_loader.pmt_to_volts by reporting which interpretation matches.
  2. bidirectional    — are alternate cycles spatially reversed between the two
     readers? (tested by reversing odd / even cycles along the sample axis)
  3. feedback x12.5    — upsample scanner feedback (sampleRateFdbk grid) onto the
     PMT grid (sampleRate). Factor = sampleRate/sampleRateFdbk, computed from
     the data (NON-integer, e.g. 12.5), so interpolation, not block-repeat.

Layouts (this is the crux):
    als_loader : pmt   [cycle, sample, channel]   scnnr [cycle, sample, XY(Z)]
    als_ref    : pmtData [sample, channel, cycle]  scannerG [sample, XY, cycle]
  -> als_loader arrays are transposed (1, 2, 0) before comparison.

Usage: edit CONFIG, then `python compare_als_ref.py`.
Pure numpy + scipy; reads als_loader from ALS_LOADER_DIR (one-way import).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.io import loadmat

# ------------------------------- CONFIG ------------------------------------ #
ALS_LOADER_DIR = r"C:\Users\Takanori Shinotsuka\GitHub\microscope_control_dev\src\python"
DATA_ROOT      = r"C:\Users\Takanori Shinotsuka\workspace\2026_microscope_control_dev"
REF_DIR        = DATA_ROOT  # where als_ref_*.mat live

# (als_ref .mat , ALS acquisition stem WITHOUT extension) -- confirmed pairing.
# NOTE: als_ref numbering is an export counter; it does NOT match the acq index.
PAIRS = [
    ("als_ref_00001.mat",
     r"20260601_sub-ref_ses-01\sub-ref_ses-01_cond-cagegfpfixed_run-01_00002"),
    ("als_ref_00003.mat",
     r"20260601_sub-ref_ses-01\sub-ref_ses-01_cond-cagegfpfixed_run-01_00003"),
]
REL_TOL = 1e-4   # relative match threshold (residual / data scale) for PASS
# --------------------------------------------------------------------------- #

sys.path.insert(0, ALS_LOADER_DIR)
import als_loader as AL  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def load_ref(mat_path: str) -> dict:
    """als_ref_*.mat was saved with `save(...,'-struct',ref)`, so the top-level
    variables ARE the fields: pmtData (N,C,F), scannerG (Nf,2,F), [scannerZ],
    sampleRate, sampleRateFdbk."""
    m = loadmat(mat_path, squeeze_me=False)
    return {
        "pmtData": np.asarray(m["pmtData"], dtype=np.float64),                       # (N, C, F)
        "scannerG": np.asarray(m["scannerG"], dtype=np.float64) if "scannerG" in m else None,
        "scannerZ": np.asarray(m["scannerZ"], dtype=np.float64) if "scannerZ" in m else None,
        "sampleRate": float(np.ravel(m["sampleRate"])[0]),
        "sampleRateFdbk": float(np.ravel(m["sampleRateFdbk"])[0]),
    }


def maxabs(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.max(np.abs(a - b))) if a.size else float("nan")


def reverse_odd(x: np.ndarray) -> np.ndarray:
    """Reverse the sample axis (0) on odd cycles (axis 2). x: (S, K, F)."""
    y = x.copy()
    y[:, :, 1::2] = x[::-1, :, 1::2]
    return y


def reverse_even(x: np.ndarray) -> np.ndarray:
    y = x.copy()
    y[:, :, 0::2] = x[::-1, :, 0::2]
    return y


def best_key(d: dict) -> str:
    return min(d, key=lambda k: (np.inf if not np.isfinite(d[k]) else d[k]))


def upsample_feedback(scnnr_native: np.ndarray, n_out: int) -> np.ndarray:
    """als_loader scnnr (F, Nf, K) -> (F, n_out, K) by per-cycle interpolation on
    normalized cycle phase. Factor (n_out/Nf) need NOT be integer."""
    F, Nf, K = scnnr_native.shape
    xp = np.linspace(0.0, 1.0, Nf, endpoint=False)
    xo = np.linspace(0.0, 1.0, n_out, endpoint=False)
    out = np.empty((F, n_out, K), dtype=np.float64)
    for f in range(F):
        for k in range(K):
            out[f, :, k] = np.interp(xo, xp, scnnr_native[f, :, k].astype(np.float64))
    return out


# --------------------------------------------------------------------------- #
# core comparison
# --------------------------------------------------------------------------- #
def compare_pair(ref_mat: str, stem: str) -> None:
    print("=" * 72)
    print(f"REF  {Path(ref_mat).name}")
    print(f"ALS  {Path(stem).name}")

    ref = load_ref(ref_mat)
    ls = AL.load(stem)
    if ls.pmt is None:
        print("!! als_loader returned no PMT data (missing .pmt.dat?)")
        return

    N, C, F = ref["pmtData"].shape
    print(f"ref pmt (N,C,F)        : {(N, C, F)}")
    print(f"als pmt (F,N,C)        : {ls.pmt.shape}")
    print(f"rates ref pmt/fdbk     : {ref['sampleRate']:.0f} / {ref['sampleRateFdbk']:.0f}"
          f"  (x{ref['sampleRate'] / ref['sampleRateFdbk']:g})")
    print(f"rates als pmt/fdbk     : {ls.info.pmt_sample_rate:.0f} / {ls.info.fdbk_sample_rate:.0f}")
    if ls.pmt.shape != (F, N, C):
        print(f"!! shape mismatch: als {ls.pmt.shape} vs expected {(F, N, C)} "
              f"(transpose of ref). Check channelSave / lineScanSamplesPerFrame.")
        return

    # ---- PMT: resolve offset pre/post (and counts vs volts) -----------------
    raw = np.transpose(ls.pmt.astype(np.float64), (1, 2, 0))           # (N, C, F)
    offs = np.asarray(AL._as_list(ls.info.channel_offsets)[:C], dtype=np.float64)
    cands: dict[str, np.ndarray] = {"raw_counts": raw}
    if offs.size == C:
        cands["counts_minus_offset"] = raw - offs.reshape(1, C, 1)
    # volts interpretations (only if input ranges are present)
    try:
        cands["volts_raw"] = np.transpose(
            AL.pmt_to_volts(ls.pmt, ls.info, subtract_offset=False), (1, 2, 0))
        cands["volts_offset"] = np.transpose(
            AL.pmt_to_volts(ls.pmt, ls.info, subtract_offset=True), (1, 2, 0))
    except Exception as e:
        print(f"   (volts conversion skipped: {e})")

    print(f"channel_offsets        : {offs.tolist() if offs.size else '(none in meta)'}")
    # JOINT search over interpretation x orientation -- offset and bidirectional
    # must be resolved together (a wrong-scale interp can otherwise beat the true
    # one once its cycles are reversed). Take the global minimum.
    orients = {"as_is": (lambda a: a), "odd_reversed": reverse_odd, "even_reversed": reverse_even}
    grid = {(ik, ok): maxabs(ref["pmtData"], ofn(iv))
            for ik, iv in cands.items() for ok, ofn in orients.items()}
    interp, orient = min(grid, key=grid.get)
    best_res = grid[(interp, orient)]
    scale = max(1.0, float(np.max(np.abs(ref["pmtData"]))))
    pmt_rel = best_res / scale
    print("PMT residual (max|delta|), best orientation per interpretation:")
    for ik in cands:
        bo = min(orients, key=lambda ok: grid[(ik, ok)])
        print(f"   {ik:22s}: {grid[(ik, bo)]:.6g}  ({bo})")
    print(f"PMT verdict            : {'PASS' if pmt_rel < REL_TOL else 'CHECK'}"
          f"  interp='{interp}', orient='{orient}', max|delta|={best_res:.6g}, rel={pmt_rel:.2e}")

    # ---- scanner feedback (native grid) + x12.5 upsample --------------------
    if ls.scnnr is not None and ref["scannerG"] is not None:
        scn = np.transpose(ls.scnnr.astype(np.float64), (1, 2, 0))     # (Nf, K, F)
        g = scn[:, :2, :]
        sb = {
            "as_is": maxabs(ref["scannerG"], g),
            "odd_reversed": maxabs(ref["scannerG"], reverse_odd(g)),
            "even_reversed": maxabs(ref["scannerG"], reverse_even(g)),
        }
        s_orient = best_key(sb)
        s_scale = max(1e-9, float(np.max(np.abs(ref["scannerG"]))))
        s_rel = sb[s_orient] / s_scale
        print(f"scanner native ref/als : {ref['scannerG'].shape} / {g.shape}")
        print(f"scanner G residual     : {sb} -> '{s_orient}'")
        print(f"scanner verdict        : {'PASS' if s_rel < REL_TOL else 'CHECK'}"
              f"  (rel={s_rel:.2e}, orient='{s_orient}')")
        if ref["scannerZ"] is not None and scn.shape[1] > 2:
            print(f"scanner Z residual     : {maxabs(ref['scannerZ'], scn[:, 2:3, :]):.6g}")

        factor = ref["sampleRate"] / ref["sampleRateFdbk"]
        up = upsample_feedback(ls.scnnr.astype(np.float64), N)
        print(f"feedback upsample      : x{factor:g}  Nf={ls.scnnr.shape[1]} -> N={up.shape[1]}"
              f"  (out {up.shape}, finite={bool(np.isfinite(up).all())})")
    else:
        print("scanner                : missing (scnnr or scannerG absent)")


def main() -> None:
    for ref_name, stem_rel in PAIRS:
        ref_mat = str(Path(REF_DIR) / ref_name)
        stem = str(Path(DATA_ROOT) / stem_rel)
        try:
            compare_pair(ref_mat, stem)
        except Exception as e:  # keep going to the next pair
            print(f"!! {ref_name}: {type(e).__name__}: {e}")
    print("=" * 72)


if __name__ == "__main__":
    main()
