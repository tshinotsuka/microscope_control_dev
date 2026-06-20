#!/usr/bin/env python
"""
fig_als_content.py -- F2: ROI map + per-ROI time course (linked by colour).

LEFT  : the 1 Hz raster reference (--raster) with the ALS scan path overlaid
        (real feedback, sweeps coloured by scan order) -- shared with F3 via
        als_overlay_panel (single source).
RIGHT : one time trace per ROI = mean intensity along that line, per cycle
        (the headline channel; EGFP by default). Colours MATCH the left overlay,
        so "this ROI on the tissue" <-> "this time course". Optional inject line.

This co-locates space (where) and time (how it evolves). The full standalone overlay
(registration QC) remains F3 (fig_als_raster_overlay.py); both share the same drawing.

Channel roles from channelSave: --srs-channel is the PD (SRS); others are EGFP/PMT.

Output -> dataset work/ (raw/ -> work/, created if missing).
Deps: numpy, matplotlib, tifffile (+ figstyle_tshino optional). Run from src/python.

Usage:
    python fig_als_content.py <raster_1hz.tif> <als_stem> --px-per-um 1.1 \
        --srs-channel 3 [--channel N] [--inject-cycle 501] [--trace-reduce mean|max]
        [--cycle 0] [--scan-cmap cool] [--scalebar-um 200] [--y-down 0|1]
        [--out-dir DIR] [--out fig.png]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

import als_raster_overlay as aro
import als_overlay_panel as P


def _apply_style():
    fs = None
    try:
        import figstyle_tshino as fs
        fs.set_style()
    except Exception:
        plt.rcParams.update({
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Liberation Sans", "Arimo", "Helvetica", "DejaVu Sans"],
            "pdf.fonttype": 42, "svg.fonttype": "none",
        })
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 10, "axes.labelsize": 9,
                         "xtick.labelsize": 8, "ytick.labelsize": 8})
    return fs


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


def main():
    ap = argparse.ArgumentParser(description="F2 ROI map + per-ROI time course")
    ap.add_argument("raster_tif")
    ap.add_argument("als_stem")
    ap.add_argument("--px-per-um", type=float, default=1.1)
    ap.add_argument("--pixel-um", type=float, default=None)
    ap.add_argument("--srs-channel", type=int, default=3)
    ap.add_argument("--channel", type=int, default=None,
                    help="headline SI channel for the traces (default: first EGFP)")
    ap.add_argument("--ref-channel", type=int, default=None, help="raster bg channel")
    ap.add_argument("--n-channels", type=int, default=None)
    ap.add_argument("--reduce", choices=["mean", "max", "first"], default="mean")
    ap.add_argument("--trace-reduce", choices=["mean", "max"], default="mean",
                    help="collapse along the line -> 1 value per cycle")
    ap.add_argument("--cycle", type=int, default=0, help="feedback cycle for the path")
    ap.add_argument("--inject-cycle", type=int, default=None, help="draw a line at this cycle")
    ap.add_argument("--time-unit", choices=["cycle", "s", "ms", "min"], default="s")
    ap.add_argument("--origin", choices=["frame", "inject"], default="frame",
                    help="x=0 at frame/scan start, or at injection (needs --inject-cycle)")
    ap.add_argument("--scan-cmap", default="cool")
    ap.add_argument("--scalebar-um", type=float, default=None)
    ap.add_argument("--y-down", choices=["1", "0"], default="1")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    fs = _apply_style()
    print("[F2] reading raster ...")
    img, rsf_field, ch_col, csave = P.read_raster(
        a.raster_tif, a.srs_channel, a.ref_channel, a.n_channels, a.reduce)
    um_per_px = a.pixel_um if a.pixel_um is not None else (1.0 / a.px_per_um if a.px_per_um else None)
    rf = aro.RasterFrame(img, rsf_field, pixel_size_um=um_per_px, y_down=(a.y_down == "1"))

    ls, sweeps, line_wins_fdbk, line_wins_pmt = P.prepare_als(a.als_stem)
    ci = max(0, min(a.cycle, ls.scnnr.shape[0] - 1))
    fb = ls.scnnr[ci][:, :2].astype(np.float64)
    M, V, R = P.fit_volts_to_ref(sweeps, line_wins_fdbk, fb)
    unit = getattr(fs, "MICRON", "um") if (fs and um_per_px is not None) else (
        "um" if um_per_px is not None else "px")
    pred = rf.px_to_axis(rf.ref_to_pixel(P._apply_affine(M, V)))
    true = rf.px_to_axis(rf.ref_to_pixel(R))
    print(f"[F2] volts->raster registration RMS = "
          f"{float(np.sqrt(((pred-true)**2).sum(1).mean())):.3g} {unit}")
    path_axis = P.feedback_axis_path(rf, M, fb)
    nsw = max(len(line_wins_fdbk), 1)
    colors = P.order_colors(nsw, a.scan_cmap)

    # headline channel column for the traces
    phys = list(ls.info.pmt_channels)
    if a.channel is not None and a.channel in phys:
        col = phys.index(a.channel)
    else:
        egfp = [i for i, p in enumerate(phys) if p != a.srs_channel]
        col = egfp[0] if egfp else 0
    head_phys = phys[col]
    ncyc = ls.pmt.shape[0]
    reduce_fn = np.mean if a.trace_reduce == "mean" else np.max

    # ---- layout: left overlay (spans rows) | right per-ROI traces ----
    rate = ls.info.cycle_rate_hz or 125.0
    cyc0 = a.inject_cycle if (a.origin == "inject" and a.inject_cycle is not None) else 0
    cycles = np.arange(ncyc)
    if a.time_unit == "cycle":
        x = cycles - cyc0
        xlabel = "cycle" + (" (rel. inject)" if cyc0 else "")
        inj_x = (a.inject_cycle - cyc0) if a.inject_cycle is not None else None
    else:
        scale = {"s": 1.0, "ms": 1000.0, "min": 1.0 / 60.0}[a.time_unit]
        x = (cycles - cyc0) / rate * scale
        xlabel = f"time ({a.time_unit})" + (" (rel. inject)" if cyc0 else "")
        inj_x = ((a.inject_cycle - cyc0) / rate * scale) if a.inject_cycle is not None else None

    fig = plt.figure(figsize=(11, max(5.5, 1.5 * nsw)))
    gs = gridspec.GridSpec(nsw, 2, width_ratios=[1.35, 1.0], wspace=0.06, hspace=0.45)
    axL = fig.add_subplot(gs[:, 0])
    P.draw_scan_path(axL, rf, line_wins_fdbk, path_axis, colors, draw_travel=True)
    fov_w = rf.nx * (rf.pixel_size_um if um_per_px is not None else 1.0)
    sb = a.scalebar_um or P.nice_len(fov_w / 5.0)
    P.scale_bar(axL, sb)
    axL.set_axis_off()

    axes_r = []
    for k, (nm, p0, p1) in enumerate(line_wins_pmt):
        ax = fig.add_subplot(gs[k, 1], sharex=axes_r[0] if axes_r else None)
        axes_r.append(ax)
        tr = reduce_fn(ls.pmt[:, p0:min(p1, ls.pmt.shape[1]), col].astype(np.float64), axis=1)
        ax.plot(x, tr, color=colors[k], lw=0.9)
        if inj_x is not None:
            ax.axvline(inj_x, color="#d62728", lw=1.2, zorder=5)
        # ROI tag ABOVE each trace (in the gap) -> never overlaps the data
        ax.text(0.0, 1.06, f"{k + 1}. {nm}", transform=ax.transAxes, ha="left", va="bottom",
                color=colors[k], fontsize=8, fontweight="bold")
        ax.grid(True, alpha=0.25)
        if k == nsw // 2:
            ax.set_ylabel("counts")
        if k < nsw - 1:
            plt.setp(ax.get_xticklabels(), visible=False)
    axes_r[-1].set_xlabel(xlabel)

    egfp = csave[ch_col] if csave else "?"
    inj_txt = "  (red = inject)" if a.inject_cycle is not None else ""
    fig.suptitle(f"{os.path.basename(ls.stem)}  --  ALS {rate:g} Hz, {ncyc} cyc, {nsw} ROIs\n"
                 f"left: ROI map (EGFP Ch{egfp}, scale bar {sb:g} {unit})  |  "
                 f"right: per-ROI {a.trace_reduce} along line, Ch{head_phys} (EGFP), "
                 f"x = {xlabel}{inj_txt}", fontsize=11, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))

    if a.out:
        out = a.out; Path(out).parent.mkdir(parents=True, exist_ok=True)
    else:
        outdir = Path(a.out_dir) if a.out_dir else _work_dir(a.als_stem)
        outdir.mkdir(parents=True, exist_ok=True)
        out = str(outdir / (os.path.basename(ls.stem) + "_F2_roi_dynamics.png"))
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(os.path.splitext(out)[0] + ".pdf", bbox_inches="tight")
    print(f"[F2] wrote {out}  (+ .pdf)")


if __name__ == "__main__":
    main()
