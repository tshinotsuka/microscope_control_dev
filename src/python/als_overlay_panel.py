"""
als_overlay_panel.py -- shared ALS-on-raster overlay (used by F2 left panel & F3).

Single source for: reading the 1Hz raster .tif, registering the ALS scanner feedback
to the raster (volts->reference affine fit from each sweep line's geometry<->feedback
correspondence), and drawing the registered scan path coloured by scan order. Callers
add their own legend / scale bar / title.

Reuses als_raster_overlay (RasterFrame/ScanField/ref_to_pixel/px_to_axis) for the
tested calibration-free geometry, and als_loader for parsing.
"""
from __future__ import annotations

import numpy as np
import matplotlib

import als_loader as al
import als_raster_overlay as aro


# ---------- raster ----------
def read_raster(tif, srs_ch=3, ref_ch=None, n_ch_override=None, reduce="mean"):
    """Return (image2D, raster_ScanField, ch_col, channelSave)."""
    import tifffile
    arr = tifffile.imread(tif)
    md = {}
    try:
        with tifffile.TiffFile(tif) as tf:
            md = tf.scanimage_metadata or {}
    except Exception as e:
        print(f"  [R1] scanimage_metadata read failed: {e}")
    fd = md.get("FrameData", {}) if isinstance(md, dict) else {}
    csave = fd.get("SI.hChannels.channelSave")
    if isinstance(csave, (int, float)):
        csave = [int(csave)]
    elif isinstance(csave, (list, tuple)):
        csave = [int(c) for c in csave]
    else:
        csave = []
    n_ch = n_ch_override or (len(csave) if csave else 1)
    if ref_ch is not None and ref_ch in csave:
        ch_col = csave.index(ref_ch)
    elif csave:
        egfp = [i for i, c in enumerate(csave) if c != srs_ch]
        ch_col = egfp[0] if egfp else 0
    else:
        ch_col = 0
    red = {"mean": lambda a: a.mean(0), "max": lambda a: a.max(0), "first": lambda a: a[0]}[reduce]
    if arr.ndim == 2:
        img = arr.astype(np.float64)
    elif arr.ndim == 3:
        frames = arr[ch_col::n_ch] if n_ch > 1 else arr
        img = red(frames.astype(np.float64))
    elif arr.ndim == 4:
        img = red(arr[:, ch_col].astype(np.float64))
    else:
        raise SystemExit(f"unexpected raster ndim={arr.ndim} shape={arr.shape}")
    try:
        rsf = al.scanfields({"RoiGroups": md["RoiGroups"]})[0]
    except Exception as e:
        raise SystemExit(f"[R1] could not parse raster RoiGroups: {e}")
    rsf_field = aro.ScanField(center=tuple(rsf["center_xy"]), size=tuple(rsf["size_xy"]),
                              rotation_deg=rsf.get("rotation_deg") or 0.0,
                              name=rsf.get("name") or "raster")
    print(f"  [R2] raster arr.shape={arr.shape} n_ch={n_ch} ch_col={ch_col} "
          f"channelSave={csave} -> image{img.shape} reduce={reduce}")
    print(f"  [R1] raster scanfield: center={rsf_field.center} size={rsf_field.size} "
          f"rot={rsf_field.rotation_deg}")
    return img, rsf_field, ch_col, csave


# ---------- ALS prepare ----------
def prepare_als(als_stem):
    """Return (ls, sweeps[(name,ScanField)], line_wins_fdbk[(name,f0,f1)],
    line_wins_pmt[(name,p0,p1)])."""
    ls = al.load(als_stem)
    sfs = al.scanfields(ls.roi_group)
    sweeps = []
    for i, s in enumerate(sfs):
        fn = (s.get("function") or "").lower()
        if "line" in fn or not fn:
            sweeps.append((s.get("name") or f"L{i}",
                           aro.ScanField(center=tuple(s["center_xy"]), size=tuple(s["size_xy"]),
                                         rotation_deg=s.get("rotation_deg") or 0.0,
                                         name=s.get("name") or f"L{i}", order=i, kind="line")))
    seg = al.segment_samples(ls.si, ls.roi_group)["segments"]
    line_segs = [s for s in seg if "line" in (s["function"] or "").lower()]
    line_wins_fdbk = [(s["name"], s["fdbk"][0], s["fdbk"][1]) for s in line_segs]
    line_wins_pmt = [(s["name"], s["pmt"][0], s["pmt"][1]) for s in line_segs]
    return ls, sweeps, line_wins_fdbk, line_wins_pmt


# ---------- registration (volts -> reference, affine) ----------
def _affine_fit(v, r):
    vh = np.hstack([np.asarray(v, float)[:, :2], np.ones((len(v), 1))])
    M, *_ = np.linalg.lstsq(vh, np.asarray(r, float), rcond=None)
    return M


def _apply_affine(M, v):
    vh = np.hstack([np.asarray(v, float)[:, :2], np.ones((len(v), 1))])
    return vh @ M


def fit_volts_to_ref(sweeps, line_wins_fdbk, fb):
    """coarse(center) -> per-line orientation -> dense least-squares affine."""
    cen_v = [fb[w0:w1].mean(0) for (_, w0, w1) in line_wins_fdbk]
    cen_r = [np.asarray(sf.center, float) for _, sf in sweeps]
    Mc = _affine_fit(np.array(cen_v), np.array(cen_r))
    Vs, Rs = [], []
    for (_, w0, w1), (_, sf) in zip(line_wins_fdbk, sweeps):
        v = fb[w0:w1]
        A, B = (np.asarray(p, float) for p in sf.entry_exit())
        e0 = _apply_affine(Mc, v[:1])[0]; e1 = _apply_affine(Mc, v[-1:])[0]
        if np.hypot(*(e0 - A)) + np.hypot(*(e1 - B)) <= np.hypot(*(e0 - B)) + np.hypot(*(e1 - A)):
            A2, B2 = A, B
        else:
            A2, B2 = B, A
        t = np.linspace(0, 1, len(v))[:, None]
        Vs.append(v); Rs.append((1 - t) * A2 + t * B2)
    M = _affine_fit(np.vstack(Vs), np.vstack(Rs))
    return M, np.vstack(Vs), np.vstack(Rs)


def feedback_axis_path(rf, M, fb):
    """map volts feedback -> reference -> raster pixel -> axis (um or px)."""
    ref = _apply_affine(M, fb)
    return rf.px_to_axis(rf.ref_to_pixel(np.asarray(ref, float)))


def order_colors(n, cmap_name="cool"):
    cmap = matplotlib.cm.get_cmap(cmap_name)
    return [cmap(k / max(n - 1, 1)) for k in range(n)]


def draw_scan_path(ax, rf, line_wins_fdbk, path_axis, colors, draw_travel=True, lw=2.6):
    """imshow raster + travel(dotted) + sweeps(solid, coloured). returns line handles."""
    ax.imshow(rf.image, cmap="gray", extent=rf.extent_for_imshow(),
              origin="upper", interpolation="nearest")
    if draw_travel:
        ax.plot(path_axis[:, 0], path_axis[:, 1], ls=":", lw=0.9, color="0.6", zorder=2)
    handles = []
    for k, (nm, w0, w1) in enumerate(line_wins_fdbk):
        seg = path_axis[w0:w1]
        ln, = ax.plot(seg[:, 0], seg[:, 1], "-", color=colors[k], lw=lw, alpha=0.95,
                      zorder=4, label=f"{k + 1}. {nm}")
        handles.append(ln)
    ax.set_aspect("equal")
    return handles


def scale_bar(ax, length, color="white", frac=0.06):
    """bar only at lower-right (length in axis/data units)."""
    xr = sorted(ax.get_xlim()); yr = sorted(ax.get_ylim())
    W = xr[1] - xr[0]; H = yr[1] - yr[0]
    x1 = xr[1] - frac * W; x0 = x1 - length; yb = yr[1] - 0.07 * H
    ax.plot([x0, x1], [yb, yb], "-", color=color, lw=3.5, solid_capstyle="butt", zorder=8)


def nice_len(x):
    import math
    if x <= 0:
        return 1.0
    e = math.floor(math.log10(x)); b = x / 10 ** e
    for m in (1, 2, 5):
        if b <= m:
            return float(m * 10 ** e)
    return float(10 ** (e + 1))
