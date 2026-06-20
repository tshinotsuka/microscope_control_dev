#!/usr/bin/env python
"""
fig_als_raster_overlay.py -- F3: standalone ALS scan path on the 1Hz raster.

Thin wrapper over als_overlay_panel (single source shared with F2's left panel):
reads the raster .tif, registers the real scanner feedback to it (volts->reference
affine), and draws the registered scan path coloured by scan order. Adds an
OUTSIDE upper-right legend (scan order top-to-bottom) and a lower-right scale bar
(bar only; length in title). No text inside the image.

- raster .tif passed EXPLICITLY (which idx is the 1 Hz reference varies run-to-run).
- pixel size as px/um (1.1 px/um => 0.909 um/px). --scalebar-um sets the bar length.
- output -> dataset work/ (raw/ -> work/, created if missing).

Deps: numpy, matplotlib, tifffile (+ figstyle_tshino optional). Run from src/python.

Usage:
    python fig_als_raster_overlay.py <raster_1hz.tif> <als_stem> --px-per-um 1.1 \
        --srs-channel 3 [--cycle 0] [--ref-channel N] [--scan-cmap cool]
        [--scalebar-um 200] [--no-travel] [--hide-axes] [--y-down 0|1]
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
from matplotlib.lines import Line2D

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
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10,
                         "xtick.labelsize": 9, "ytick.labelsize": 9})
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
    ap = argparse.ArgumentParser(description="F3 ALS-on-raster overlay (standalone)")
    ap.add_argument("raster_tif")
    ap.add_argument("als_stem")
    ap.add_argument("--px-per-um", type=float, default=1.1)
    ap.add_argument("--pixel-um", type=float, default=None)
    ap.add_argument("--srs-channel", type=int, default=3)
    ap.add_argument("--ref-channel", type=int, default=None)
    ap.add_argument("--n-channels", type=int, default=None)
    ap.add_argument("--reduce", choices=["mean", "max", "first"], default="mean")
    ap.add_argument("--cycle", type=int, default=0)
    ap.add_argument("--scan-cmap", default="cool")
    ap.add_argument("--scalebar-um", type=float, default=None)
    ap.add_argument("--no-travel", action="store_true")
    ap.add_argument("--hide-axes", action="store_true")
    ap.add_argument("--y-down", choices=["1", "0"], default="1")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    fs = _apply_style()
    print("[F3] reading raster ...")
    img, rsf_field, ch_col, csave = P.read_raster(
        a.raster_tif, a.srs_channel, a.ref_channel, a.n_channels, a.reduce)
    um_per_px = a.pixel_um if a.pixel_um is not None else (1.0 / a.px_per_um if a.px_per_um else None)
    if um_per_px is not None:
        print(f"[F3] pixel size: {um_per_px:.4g} um/px"
              + (f"  (= {a.px_per_um:g} px/um)" if a.pixel_um is None else ""))
    rf = aro.RasterFrame(img, rsf_field, pixel_size_um=um_per_px, y_down=(a.y_down == "1"))

    ls, sweeps, line_wins_fdbk, _ = P.prepare_als(a.als_stem)
    ci = max(0, min(a.cycle, ls.scnnr.shape[0] - 1))
    fb = ls.scnnr[ci][:, :2].astype(np.float64)
    M, V, R = P.fit_volts_to_ref(sweeps, line_wins_fdbk, fb)
    unit = getattr(fs, "MICRON", "um") if (fs and um_per_px is not None) else (
        "um" if um_per_px is not None else "px")
    pred = rf.px_to_axis(rf.ref_to_pixel(P._apply_affine(M, V)))
    true = rf.px_to_axis(rf.ref_to_pixel(R))
    print(f"[F3] volts->raster registration RMS = "
          f"{float(np.sqrt(((pred-true)**2).sum(1).mean())):.3g} {unit}")
    path_axis = P.feedback_axis_path(rf, M, fb)
    nsw = max(len(line_wins_fdbk), 1)
    colors = P.order_colors(nsw, a.scan_cmap)

    fig, ax = plt.subplots(figsize=(6.4, 6.4))
    handles = P.draw_scan_path(ax, rf, line_wins_fdbk, path_axis, colors,
                               draw_travel=not a.no_travel, lw=2.8)
    fov_w = rf.nx * (rf.pixel_size_um if um_per_px is not None else 1.0)
    sb = a.scalebar_um or P.nice_len(fov_w / 5.0)
    P.scale_bar(ax, sb)
    if not a.no_travel:
        handles.append(Line2D([0], [0], ls=":", color="0.6", label="travel"))
    leg = ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0),
                    fontsize=8, framealpha=0.9, title="scan order", borderaxespad=0.0)
    if a.hide_axes:
        ax.set_axis_off()
    else:
        ax.set_xlabel(f"x ({unit})"); ax.set_ylabel(f"y ({unit})")
    egfp = csave[ch_col] if csave else "?"
    ax.set_title(f"ALS scan path (real feedback) on 1Hz reference (EGFP Ch{egfp})  --  "
                 f"{nsw} sweeps, order 1..{nsw}  |  scale bar {sb:g} {unit}\n"
                 f"{os.path.basename(ls.stem)}", fontsize=10, loc="left")

    fig.tight_layout()
    if a.out:
        out = a.out; Path(out).parent.mkdir(parents=True, exist_ok=True)
    else:
        outdir = Path(a.out_dir) if a.out_dir else _work_dir(a.als_stem)
        outdir.mkdir(parents=True, exist_ok=True)
        out = str(outdir / (os.path.basename(ls.stem) + "_F3_overlay.png"))
    fig.savefig(out, dpi=300, bbox_inches="tight", bbox_extra_artists=(leg,))
    fig.savefig(os.path.splitext(out)[0] + ".pdf", bbox_inches="tight", bbox_extra_artists=(leg,))
    print(f"[F3] wrote {out}  (+ .pdf)")


if __name__ == "__main__":
    main()
