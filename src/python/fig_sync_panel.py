#!/usr/bin/env python
"""
fig_sync_panel.py -- F1: sync panel (report quality) + injection zoom

From one Data Recorder .h5, overlay injector TTL (deterministic injection),
cycle/frame clock, and behavior (treadmill_dir/speed) on ONE recorder-relative
timebase, annotated with inject_cycle and head_pad. Also writes a separate
zoom figure around the injection showing the injector edge landing on the
cycle-clock rising edge (+0.0 ms => frame-clock-anchored).

Numbers (inject_cycle / head_pad / rate) come from qc_core (== contract / dashboard /
sidecar, same #501 & head_pad). Traces come from datarecorder_loader.

All figure text is ASCII so it renders without a CJK font (avoids tofu/garbled).

Deps: numpy, matplotlib, h5py (ivwib or mcd-quicklook). Run from the same
src/python (sibling import of qc_core / datarecorder_loader).

Usage:
    python fig_sync_panel.py <recorder.h5> [als_stem] [--out fig.png]
        [--zoom-ms 40] [--title "..."]
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import datarecorder_loader as DR
import qc_core

TTL_NAME = "Legato130_TTL"
CLOCK_NAME = "frame_clock"
RED = "#d62728"
BAND = (1.0, 0.78, 0.0, 0.18)


def _ctx(h5, als_stem):
    """Load qc numbers + raw traces once."""
    qc = qc_core.qc_load(h5, als_stem, ttl_name=TTL_NAME, clock_name=CLOCK_NAME)
    data = DR.load_datarecorder(h5)
    fs = data["samplerate"] or 1.0
    n = max((data["signals"][nm].size for nm in data["names"]), default=0)
    t = np.arange(n) / fs
    inj = qc.get("injector") or {}
    tm = qc.get("timing") or {}
    return {
        "qc": qc, "data": data, "fs": fs, "t": t,
        "x0": (inj.get("sample_index") / fs) if inj.get("sample_index") is not None else None,
        "head_pad": tm.get("head_pad_s"),
        "cyc": tm.get("inject_index_1based"),
        "off": tm.get("inject_offset_ms"),
        "rate": tm.get("rate_hz"),
        "ncyc": tm.get("n"),
        "ncmd": tm.get("n_commanded"),
        "lbl": "cycle" if tm.get("mode") == "als" else "frame",
        "t0_txt": inj.get("t0_recorder_s"),
    }


def make_overview(ctx, out, title=None):
    data, fs, t = ctx["data"], ctx["fs"], ctx["t"]
    x0, head_pad, cyc, off = ctx["x0"], ctx["head_pad"], ctx["cyc"], ctx["off"]
    lbl = ctx["lbl"]
    behavior = [nm for nm in data["names"] if nm not in (TTL_NAME, CLOCK_NAME)]
    have_clock = CLOCK_NAME in data["signals"]
    have_ttl = TTL_NAME in data["signals"]

    plt.rcParams.update({"font.size": 11, "axes.titlesize": 11, "axes.labelsize": 10,
                         "xtick.labelsize": 9, "ytick.labelsize": 9, "axes.grid": True,
                         "grid.alpha": 0.25})
    nrow = int(have_ttl) + int(have_clock) + int(bool(behavior))
    fig, axes = plt.subplots(nrow, 1, figsize=(10, 2.2 * nrow), sharex=True)
    axes = list(np.atleast_1d(axes)); ai = 0

    def mark(ax):
        if head_pad:
            ax.axvspan(0.0, head_pad, color=BAND, lw=0, zorder=0)
        if x0 is not None:
            ax.axvline(x0, color=RED, lw=2, zorder=5)

    if have_ttl:
        ax = axes[ai]; ai += 1
        ax.plot(t, data["signals"][TTL_NAME], color="#1f77b4", lw=0.8); mark(ax)
        ax.set_ylabel("injector\nTTL (V)")
        cyc_txt = f"cycle #{cyc} (+{off} ms)" if cyc is not None else "n.a."
        ax.set_title(f"injector  --  t0 = {ctx['t0_txt']} s,  inject @ {cyc_txt}", loc="left")
        if x0 is not None and cyc is not None:
            ax.annotate(f"inject @ {lbl} #{cyc}", xy=(x0, ax.get_ylim()[1]),
                        xytext=(6, -4), textcoords="offset points",
                        color=RED, fontsize=9, va="top", fontweight="bold")

    if have_clock:
        ax = axes[ai]; ai += 1
        ax.plot(t, data["signals"][CLOCK_NAME], color="#2ca02c", lw=0.5); mark(ax)
        ax.set_ylabel(f"{lbl} clock\n(V)")
        nc = f" / {ctx['ncmd']} commanded" if ctx["ncmd"] else ""
        ax.set_title(f"{lbl} clock  --  {ctx['ncyc']}{nc} {lbl}s @ {ctx['rate']} Hz "
                     f"(yellow band = head_pad: recorder start -> first {lbl})", loc="left")
        if head_pad:
            ax.annotate(f"head_pad = {head_pad} s", xy=(head_pad, ax.get_ylim()[1]),
                        xytext=(-6, -4), textcoords="offset points",
                        ha="right", va="top", fontsize=9, color="#8a6d00")

    if behavior:
        ax = axes[ai]; ai += 1
        for i, nm in enumerate(behavior):
            ax.plot(t, data["signals"][nm], lw=0.7, color=plt.cm.tab10(i % 10), label=nm)
        mark(ax)
        ax.set_ylabel("behavior\n(V)")
        ax.legend(loc="upper right", fontsize=8, framealpha=0.6)
        ax.set_title("behavior (treadmill)  --  same HDF5, same clock "
                     "(note: noise onset at scan start = candidate scanner EMI)", loc="left")

    axes[-1].set_xlabel("time (s, recorder-relative)")
    axes[0].set_xlim(t[0], t[-1] if t.size else 1)

    sup = title or os.path.basename(out).replace("_F1_sync.png", "")
    if cyc is not None and head_pad is not None:
        sup += (f"\ndeterministic injection: head_pad {head_pad} s -> inject @ {lbl} #{cyc} "
                f"(+{off} ms), frame-clock-anchored")
    fig.suptitle(sup, fontsize=12, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(os.path.splitext(out)[0] + ".pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"[F1] wrote {out}  (+ .pdf)")


def make_zoom(ctx, out, zoom_ms=40.0):
    data, fs, t = ctx["data"], ctx["fs"], ctx["t"]
    x0, cyc, off, lbl = ctx["x0"], ctx["cyc"], ctx["off"], ctx["lbl"]
    if x0 is None or CLOCK_NAME not in data["signals"] or TTL_NAME not in data["signals"]:
        print("[F1-zoom] skipped (need injector + clock + inject t0)")
        return
    w = zoom_ms / 1000.0
    m = (t >= x0 - w) & (t <= x0 + w)
    tms = (t[m] - x0) * 1000.0

    edges = DR.rising_edges(data["signals"][CLOCK_NAME])     # sample indices
    edges_s = edges / fs
    em = (edges_s >= x0 - w) & (edges_s <= x0 + w)
    edge_ms = (edges_s[em] - x0) * 1000.0
    edge_cyc = np.flatnonzero(em) + 1                         # 1-based cycle number

    fig, (a0, a1) = plt.subplots(2, 1, figsize=(8, 4.4), sharex=True)
    a0.plot(tms, data["signals"][TTL_NAME][m], color="#1f77b4", lw=1.2)
    a0.axvline(0.0, color=RED, lw=2)
    a0.set_ylabel("injector\nTTL (V)")
    a0.set_title(f"injection zoom  --  inject @ {lbl} #{cyc} (+{off} ms into the {lbl})",
                 loc="left")
    a0.grid(True, alpha=0.25)

    a1.plot(tms, data["signals"][CLOCK_NAME][m], color="#2ca02c", lw=1.2)
    a1.axvline(0.0, color=RED, lw=2, label="inject")
    ytop = a1.get_ylim()[1]
    for e, c in zip(edge_ms, edge_cyc):
        a1.axvline(e, color="#2ca02c", lw=0.8, ls="--", alpha=0.7)
        a1.annotate(f"#{c}", xy=(e, ytop), xytext=(2, -2), textcoords="offset points",
                    fontsize=8, color="#1a7a1a", va="top")
    a1.set_ylabel(f"{lbl} clock\n(V)")
    a1.set_xlabel("time relative to inject (ms)")
    a1.grid(True, alpha=0.25)
    a1.legend(loc="lower right", fontsize=8)

    fig.suptitle(f"inject edge lands on the {lbl} #{cyc} rising edge  (+{off} ms)",
                 fontsize=11, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    zout = os.path.splitext(out)[0] + "_zoom.png"
    fig.savefig(zout, dpi=300, bbox_inches="tight")
    fig.savefig(os.path.splitext(zout)[0] + ".pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"[F1-zoom] wrote {zout}  (+ .pdf)  | window +/-{zoom_ms:g} ms")


def main():
    ap = argparse.ArgumentParser(description="F1 sync panel + injection zoom")
    ap.add_argument("h5")
    ap.add_argument("als_stem", nargs="?", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--zoom-ms", type=float, default=40.0, help="zoom half-window (ms)")
    ap.add_argument("--title", default=None)
    a = ap.parse_args()

    ctx = _ctx(a.h5, a.als_stem)
    out = a.out or (os.path.splitext(a.h5)[0] + "_F1_sync.png")
    make_overview(ctx, out, title=a.title)
    make_zoom(ctx, out, zoom_ms=a.zoom_ms)
    for w in ctx["qc"].get("warnings", []):
        print(f"  ! {w}")


if __name__ == "__main__":
    main()
