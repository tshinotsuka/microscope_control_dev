#!/usr/bin/env python3
"""emi_quant.py -- quantify scanner-EMI on the behavior channels (C4).

Splits a Data Recorder .h5 into the IDLE window (head_pad: recorder-start -> first
cycle, scanner quiet) and the SCAN window (first -> last cycle, scanner active)
using the frame_clock pulse train, then reports per-behavior-channel noise
(AC-RMS = std about the mean) in each window, their ratio, and the scan-window
averaged spectrum with cycle-rate harmonics flagged. The EMI 'step' = std_scan /
std_idle is the headline number: how much the scanner lifts the behavior floor.

Also supports a true baseline: --compare <scanner_off.h5> prints the off-floor
std per channel for side-by-side with the scan window.

Standalone -- reads the .h5 directly (h5py), no project loaders. Runs in
mcd-quicklook or ivwib. deps: h5py, numpy, matplotlib (only with --fig).

usage:
  python emi_quant.py "<als_grab>.h5"
  python emi_quant.py "<als_grab>.h5" --fig
  python emi_quant.py "<scan_on>.h5" --compare "<scanner_off>.h5"
  flags: --clock-name frame_clock --ttl-name Legato130_TTL
         --channels treadmill_dir,treadmill_speed --out-dir <dir> --seg-s 1.0
"""
import argparse
import os
import sys

import numpy as np
import h5py


# ---------------------------------------------------------------- io / dsp
def load_h5(path):
    sig, fs = {}, None
    with h5py.File(path, "r") as f:
        a = f.attrs.get("samplerate", None)
        fs = float(a) if a is not None else None
        for k in f.keys():
            try:
                sig[k] = np.asarray(f[k][()], dtype=float).ravel()
            except Exception:
                pass
    return sig, fs


MIN_LOGIC_SWING_V = 0.5   # a real frame_clock is a 0->5V TTL; below this = noise


def rising_edges(x):
    """indices of low->high crossings of the midpoint threshold.

    Requires a real logic swing (>0.5V): a noise-only clock channel (e.g. a
    raster ref where no pulse train was recorded) must NOT yield spurious edges.
    """
    lo, hi = float(np.nanmin(x)), float(np.nanmax(x))
    if hi - lo < MIN_LOGIC_SWING_V:          # no genuine pulse train
        return np.array([], dtype=int)
    thr = 0.5 * (lo + hi)
    above = x >= thr
    return np.where(~above[:-1] & above[1:])[0] + 1


def ac_rms(x):
    x = np.asarray(x, float)
    return float(np.sqrt(np.mean((x - x.mean()) ** 2))) if x.size else float("nan")


def avg_spectrum(x, fs, seg_s=1.0):
    """Welch-ish averaged magnitude spectrum (Hann, 50% overlap). -> (f, mag)."""
    x = np.asarray(x, float)
    x = x - x.mean()
    n = x.size
    nseg = int(min(max(fs * seg_s, 256), n))
    if nseg < 16 or n < nseg:
        return np.array([]), np.array([])
    win = np.hanning(nseg)
    step = max(nseg // 2, 1)
    segs = [np.abs(np.fft.rfft(x[s:s + nseg] * win))
            for s in range(0, n - nseg + 1, step)]
    if not segs:
        return np.array([]), np.array([])
    return np.fft.rfftfreq(nseg, d=1.0 / fs), np.mean(segs, axis=0)


def top_peaks(f, mag, k=5, fmin=1.0):
    if f.size == 0:
        return []
    m = mag.copy()
    m[f < fmin] = 0.0
    idx = np.argsort(m)[::-1][:k]
    idx = idx[m[idx] > 0]
    return [(float(f[i]), float(mag[i])) for i in idx]


def is_harmonic(fp, base, tol=0.02):
    if not base or base <= 0:
        return False
    n = round(fp / base)
    return n >= 1 and abs(fp - n * base) <= tol * base


# ---------------------------------------------------------------- workdir
def work_dir_for(h5_path, out_dir):
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        return out_dir
    parts = os.path.abspath(h5_path).split(os.sep)
    if "raw" in parts:
        parts[len(parts) - 1 - parts[::-1].index("raw")] = "work"
        d = os.sep.join(parts[:-1])
    else:
        d = os.path.join(os.path.dirname(os.path.abspath(h5_path)), "work")
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="quantify scanner-EMI on behavior channels (C4)")
    ap.add_argument("h5")
    ap.add_argument("--clock-name", default="frame_clock")
    ap.add_argument("--ttl-name", default="Legato130_TTL")
    ap.add_argument("--channels", default="treadmill_dir,treadmill_speed",
                    help="comma list of behavior datasets to analyze")
    ap.add_argument("--compare", default=None, help="scanner-OFF baseline .h5")
    ap.add_argument("--seg-s", type=float, default=1.0, help="PSD segment length (s)")
    ap.add_argument("--fig", action="store_true", help="save a figure to work/")
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args()

    if not os.path.isfile(a.h5):
        sys.exit(f"ERROR: not found: {a.h5}")
    sig, fs = load_h5(a.h5)
    if fs is None:
        sys.exit(f"ERROR: {a.h5}: no root attr 'samplerate'")
    chans = [c.strip() for c in a.channels.split(",") if c.strip() and c.strip() in sig]
    if not chans:
        sys.exit(f"ERROR: none of --channels present. datasets: {list(sig)}")

    # split idle vs scan by the clock pulse train
    edges = rising_edges(sig[a.clock_name]) if a.clock_name in sig else np.array([], int)
    have_split = edges.size >= 2
    if have_split:
        i0, i1 = int(edges[0]), int(edges[-1])
        cyc_rate = fs / float(np.median(np.diff(edges)))
        t0, t1, t2 = 0.0, i0 / fs, i1 / fs
    else:
        i0 = i1 = None
        cyc_rate = None

    bar = "=" * 72
    print(bar)
    print(f"EMI quant  {os.path.basename(a.h5)}")
    if have_split:
        print(f"samplerate {fs:g} Hz | clock '{a.clock_name}': {edges.size} cycles "
              f"@ {cyc_rate:.2f} Hz")
        print(f"idle window: {t0:.3f}-{t1:.3f}s (head_pad)   "
              f"scan window: {t1:.3f}-{t2:.3f}s")
    else:
        print(f"samplerate {fs:g} Hz | clock '{a.clock_name}' has no pulse train "
              f"-> no idle/scan split (whole-record std only)")
    print("-" * 72)
    print(f"{'channel':<18}{'std_idle':>10}{'std_scan':>10}{'ratio':>8}"
          f"   top scan-locked peaks (Hz)")

    ratios, fig_rows = [], []
    for ch in chans:
        x = sig[ch]
        if have_split:
            xi, xs = x[:i0], x[i0:i1]
            si, ss = ac_rms(xi), ac_rms(xs)
            ratio = ss / si if si > 0 else float("inf")
            ratios.append(ratio)
            f, mag = avg_spectrum(xs, fs, a.seg_s)
        else:
            si = float("nan")
            ss = ac_rms(x)
            ratio = float("nan")
            f, mag = avg_spectrum(x, fs, a.seg_s)
            xi, xs = np.array([]), x
        peaks = top_peaks(f, mag, k=5, fmin=1.0)
        ptxt = ", ".join(
            f"{fp:.1f}{'*' if is_harmonic(fp, cyc_rate) else ''}" for fp, _ in peaks)
        print(f"{ch:<18}{si:>10.5f}{ss:>10.5f}"
              f"{(ratio if np.isfinite(ratio) else float('nan')):>8.2f}   {ptxt}")
        fig_rows.append((ch, xi, xs, f, mag, peaks))

    if cyc_rate:
        print(f"(* = within 2% of a cycle-rate harmonic, base {cyc_rate:.2f} Hz)")
    print("-" * 72)
    if ratios and all(np.isfinite(ratios)):
        m = float(np.mean(ratios))
        verdict = ("scanner-EMI DOMINANT on behavior" if m >= 2 else
                   "behavior floor little changed by scanning")
        print(f"EMI step (scan/idle): mean {m:.2f}x  -> {verdict}")

    # optional scanner-OFF baseline
    if a.compare:
        if not os.path.isfile(a.compare):
            print(f"[compare] not found: {a.compare}")
        else:
            csig, cfs = load_h5(a.compare)
            print("-" * 72)
            print(f"BASELINE (scanner-off) {os.path.basename(a.compare)}")
            print(f"{'channel':<18}{'std_off':>10}{'std_scan':>10}{'scan/off':>10}")
            for ch in chans:
                if ch not in csig:
                    print(f"{ch:<18}{'(absent)':>10}")
                    continue
                so = ac_rms(csig[ch])
                ss = ac_rms(sig[ch][i0:i1]) if have_split else ac_rms(sig[ch])
                r = ss / so if so > 0 else float("inf")
                print(f"{ch:<18}{so:>10.5f}{ss:>10.5f}{r:>10.2f}")
    print(bar)

    # optional figure
    if a.fig:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        for fam in (["Arial", "Liberation Sans", "Arimo", "Helvetica", "DejaVu Sans"],):
            plt.rcParams["font.sans-serif"] = fam
        plt.rcParams["pdf.fonttype"] = 42
        nch = len(fig_rows)
        fig, axes = plt.subplots(nch, 2, figsize=(11, 2.6 * nch), squeeze=False)
        for r, (ch, xi, xs, f, mag, peaks) in enumerate(fig_rows):
            axL, axR = axes[r]
            full = sig[ch]
            t = np.arange(full.size) / fs
            axL.plot(t, full, lw=0.4)
            if have_split:
                axL.axvspan(t[0], i0 / fs, color="#ffe9a8", alpha=0.7, lw=0)
            axL.set_ylabel(f"{ch}\n(V)")
            axL.set_title(f"{ch} -- yellow = idle (head_pad)", loc="left", fontsize=9)
            if f.size:
                axR.semilogy(f, mag, lw=0.7)
                if cyc_rate:
                    for n in range(1, 6):
                        axR.axvline(n * cyc_rate, color="r", ls=":", lw=0.6, alpha=0.6)
                    axR.set_xlim(0, min(6 * cyc_rate, f[-1]))
                for fp, mp in peaks:
                    axR.plot(fp, mp, "k.", ms=4)
            axR.set_title("scan-window spectrum (red = cycle harmonics)",
                          loc="left", fontsize=9)
            axR.set_ylabel("|mag|")
        axes[-1][0].set_xlabel("time (s, recorder-relative)")
        axes[-1][1].set_xlabel("frequency (Hz)")
        fig.suptitle(f"EMI quant -- {os.path.basename(a.h5)}", fontsize=11, weight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.98))
        stem = os.path.splitext(os.path.basename(a.h5))[0]
        out = os.path.join(work_dir_for(a.h5, a.out_dir), f"{stem}_emi.png")
        fig.savefig(out, dpi=150)
        print(f"[fig] {out}")


if __name__ == "__main__":
    main()
