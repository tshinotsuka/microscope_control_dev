#!/usr/bin/env python
"""
fig_recorder_panel.py -- standalone Data Recorder .h5 viewer (no ALS / no qc_core).

Same look as F1 (fig_sync_panel.py) but self-contained from a SINGLE Data Recorder
.h5: every recorded channel gets its own panel on the recorder-relative timebase.
If an injector TTL and a clock channel are present, inject@cycle#N / head_pad / rate
are derived from the .h5 itself (clock rising edges) and annotated; if absent, the
channels are simply plotted (works for a behavior-only recording too).

Use this for .h5 recorded on its own (no paired ALS .meta/.pmt/.scnnr). For an ALS
acquisition with cross-stream cycle checks, use fig_sync_panel.py (qc_core-based).

Deps: numpy, matplotlib + datarecorder_loader (sibling). Run from src/python.

Usage:
    python fig_recorder_panel.py <recorder.h5> [--ttl-name Legato130_TTL]
        [--clock-name frame_clock] [--zoom-ms 40] [--no-zoom]
        [--out fig.png] [--out-dir DIR] [--title "..."]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import datarecorder_loader as DR

RED = "#d62728"
BAND = (1.0, 0.78, 0.0, 0.18)


def _apply_style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Liberation Sans", "Arimo", "Helvetica", "DejaVu Sans"],
        "pdf.fonttype": 42, "svg.fonttype": "none",
        "font.size": 11, "axes.titlesize": 11, "axes.labelsize": 10,
        "xtick.labelsize": 9, "ytick.labelsize": 9, "axes.grid": True, "grid.alpha": 0.25,
    })


def _work_dir(inp):
    parent = Path(inp).resolve().parent
    parts = list(parent.parts)
    if "raw" in parts:
        parts[len(parts) - 1 - parts[::-1].index("raw")] = "work"
        outdir = Path(*parts)
    else:
        outdir = parent / "work"
    outdir.mkdir(parents=True, exist_ok=True)
    return outdir


def _rising(sig, thr=2.5):
    s = np.asarray(sig, float)
    return np.flatnonzero((s[:-1] < thr) & (s[1:] >= thr)) + 1


def _derive(data, fs, ttl_name, clock_name):
    """inject t0 / head_pad / rate / inject_cycle from the .h5 itself (best effort)."""
    out = dict(x0=None, head_pad=None, rate=None, ncyc=None, cyc=None, off=None, t0_txt=None)
    sig = data["signals"]
    if ttl_name in sig:
        e = _rising(sig[ttl_name])
        if e.size:
            t0i = int(e[0]); out["x0"] = t0i / fs; out["t0_txt"] = round(t0i / fs, 4)
    if clock_name in sig:
        ce = _rising(sig[clock_name])
        if ce.size:
            out["head_pad"] = round(ce[0] / fs, 4)
            out["ncyc"] = int(ce.size)
            d = np.diff(ce)
            if d.size:
                out["rate"] = round(fs / float(np.median(d)), 1)
            if out["x0"] is not None:
                t0i = int(round(out["x0"] * fs))
                k = int(np.count_nonzero(ce <= t0i))
                out["cyc"] = k
                if k >= 1:
                    out["off"] = round((t0i - ce[k - 1]) / fs * 1e3, 3)
    return out


def make_overview(data, fs, t, info, ttl_name, clock_name, out, title):
    sig = data["signals"]
    have_ttl = ttl_name in sig
    have_clk = clock_name in sig
    others = [nm for nm in data["names"] if nm not in (ttl_name, clock_name)]
    x0, head_pad, cyc, off = info["x0"], info["head_pad"], info["cyc"], info["off"]

    nrow = int(have_ttl) + int(have_clk) + len(others)
    nrow = max(nrow, 1)
    fig, axes = plt.subplots(nrow, 1, figsize=(10, 2.2 * nrow), sharex=True)
    axes = list(np.atleast_1d(axes)); ai = 0

    def mark(ax):
        if head_pad:
            ax.axvspan(0.0, head_pad, color=BAND, lw=0, zorder=0)
        if x0 is not None:
            ax.axvline(x0, color=RED, lw=2, zorder=5)

    if have_ttl:
        ax = axes[ai]; ai += 1
        ax.plot(t, sig[ttl_name], color="#1f77b4", lw=0.8); mark(ax)
        ax.set_ylabel(f"{ttl_name}\n(V)")
        cyc_txt = f"cycle #{cyc} (+{off} ms)" if cyc is not None else "n.a."
        ax.set_title(f"{ttl_name}  --  t0 = {info['t0_txt']} s,  inject @ {cyc_txt}", loc="left")
        if x0 is not None and cyc is not None:
            ax.annotate(f"inject @ cycle #{cyc}", xy=(x0, ax.get_ylim()[1]),
                        xytext=(6, -4), textcoords="offset points",
                        color=RED, fontsize=9, va="top", fontweight="bold")

    if have_clk:
        ax = axes[ai]; ai += 1
        ax.plot(t, sig[clock_name], color="#2ca02c", lw=0.5); mark(ax)
        ax.set_ylabel(f"{clock_name}\n(V)")
        rate = f"{info['rate']} Hz" if info["rate"] else "n.a."
        ncyc = info["ncyc"]
        ax.set_title(f"{clock_name}  --  {ncyc} cycles @ {rate} "
                     f"(yellow band = head_pad: recorder start -> first cycle)", loc="left")
        if head_pad:
            ax.annotate(f"head_pad = {head_pad} s", xy=(head_pad, ax.get_ylim()[1]),
                        xytext=(-6, -4), textcoords="offset points",
                        ha="right", va="top", fontsize=9, color="#8a6d00")

    for j, nm in enumerate(others):
        ax = axes[ai]; ai += 1
        ax.plot(t, sig[nm], lw=0.7, color=plt.cm.tab10(j % 10)); mark(ax)
        ax.set_ylabel(f"{nm}\n(V)")
        ax.set_title(nm, loc="left")

    axes[-1].set_xlabel("time (s, recorder-relative)")
    axes[0].set_xlim(t[0], t[-1] if t.size else 1)

    sup = title or os.path.basename(out).replace("_recorder.png", "")
    if cyc is not None and head_pad is not None:
        sup += (f"\ndeterministic injection: head_pad {head_pad} s -> inject @ cycle #{cyc} "
                f"(+{off} ms), frame-clock-anchored")
    else:
        sup += f"\nData Recorder: {len(data['names'])} channels @ {fs:g} Hz"
    fig.suptitle(sup, fontsize=12, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(os.path.splitext(out)[0] + ".pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"[rec] wrote {out}  (+ .pdf)")


def make_zoom(data, fs, t, info, ttl_name, clock_name, out, zoom_ms):
    sig = data["signals"]
    x0 = info["x0"]
    if x0 is None or clock_name not in sig or ttl_name not in sig:
        return
    w = zoom_ms / 1000.0
    m = (t >= x0 - w) & (t <= x0 + w)
    tms = (t[m] - x0) * 1000.0
    ce = _rising(sig[clock_name]); ce_s = ce / fs
    em = (ce_s >= x0 - w) & (ce_s <= x0 + w)
    edge_ms = (ce_s[em] - x0) * 1000.0
    edge_cyc = np.flatnonzero(em) + 1
    cyc = info["cyc"]

    fig, (a0, a1) = plt.subplots(2, 1, figsize=(8, 4.4), sharex=True)
    a0.plot(tms, np.asarray(sig[ttl_name])[m], color="#1f77b4", lw=1.2)
    a0.axvline(0.0, color=RED, lw=2)
    a0.set_ylabel(f"{ttl_name}\n(V)")
    a0.set_title(f"injection zoom  --  inject @ cycle #{cyc} (+{info['off']} ms into the cycle)",
                 loc="left")
    a0.grid(True, alpha=0.25)
    a1.plot(tms, np.asarray(sig[clock_name])[m], color="#2ca02c", lw=1.2)
    a1.axvline(0.0, color=RED, lw=2, label="inject")
    ytop = a1.get_ylim()[1]
    for e, c in zip(edge_ms, edge_cyc):
        a1.axvline(e, color="#2ca02c", lw=0.8, ls="--", alpha=0.7)
        a1.annotate(f"#{c}", xy=(e, ytop), xytext=(2, -2), textcoords="offset points",
                    fontsize=8, color="#1a7a1a", va="top")
    a1.set_ylabel(f"{clock_name}\n(V)")
    a1.set_xlabel("time relative to inject (ms)")
    a1.grid(True, alpha=0.25); a1.legend(loc="lower right", fontsize=8)
    fig.suptitle(f"inject edge lands on cycle #{cyc} rising edge  (+{info['off']} ms)",
                 fontsize=11, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    zout = os.path.splitext(out)[0] + "_zoom.png"
    fig.savefig(zout, dpi=300, bbox_inches="tight")
    fig.savefig(os.path.splitext(zout)[0] + ".pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"[rec-zoom] wrote {zout}  (+ .pdf)")


def main():
    ap = argparse.ArgumentParser(description="standalone Data Recorder .h5 viewer")
    ap.add_argument("h5")
    ap.add_argument("--ttl-name", default="Legato130_TTL")
    ap.add_argument("--clock-name", default="frame_clock")
    ap.add_argument("--zoom-ms", type=float, default=40.0)
    ap.add_argument("--no-zoom", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--title", default=None)
    a = ap.parse_args()

    _apply_style()
    data = DR.load_datarecorder(a.h5)
    fs = data["samplerate"] or 1.0
    n = max((data["signals"][nm].size for nm in data["names"]), default=0)
    t = np.arange(n) / fs
    info = _derive(data, fs, a.ttl_name, a.clock_name)

    if a.out:
        out = a.out; Path(out).parent.mkdir(parents=True, exist_ok=True)
    else:
        outdir = Path(a.out_dir) if a.out_dir else _work_dir(a.h5)
        outdir.mkdir(parents=True, exist_ok=True)
        out = str(outdir / (os.path.splitext(os.path.basename(a.h5))[0] + "_recorder.png"))

    make_overview(data, fs, t, info, a.ttl_name, a.clock_name, out, a.title)
    if not a.no_zoom:
        make_zoom(data, fs, t, info, a.ttl_name, a.clock_name, out, a.zoom_ms)
    print(f"[rec] channels: {data['names']}  fs={fs:g} Hz"
          + (f"  inject@cycle#{info['cyc']} head_pad={info['head_pad']}s"
             if info["cyc"] is not None else "  (no inject/clock annotation)"))


if __name__ == "__main__":
    main()
