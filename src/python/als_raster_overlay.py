"""
als_raster_overlay — register ALS scan lines / ROIs onto a raster reference image.

Position in the project
-----------------------
- Analysis repo `in_vivo_water_imaging_brain`, package `ivwib` (visualization layer,
  Track-W). Fulfils the roadmap §必要実データ(Track-W) task "ALS の ROI 位置・スキャンパスを
  1 Hz 参照画像へ overlay"（2026-06-08 起票）and handoff §4-2② "ALS×raster 一枚図".
- It is mode-general (§2 撮像モード方針): the "raster reference" can be a galvo 1 Hz frame
  today or a galvo-resonant 100 Hz frame after hardware return — same code, the only
  input that changes is the RasterFrame.

Design contract (why this is correct)
-------------------------------------
1. REGISTRATION IS CALIBRATION-FREE. Both the ALS scanfields and the raster frame are
   produced by the same instrument in the SAME ScanImage *reference* coordinate space
   (objective + zoom fix that space). Placing a line on the raster therefore needs only
   reference→pixel affines derived from each field's own (center, size, rotation). It does
   NOT need PIXEL_SIZE_UM. This matches the project px/µm discipline (roadmap §2-4):
   physical µm is a *separate* layer applied at draw time via the image extent, exactly so
   a missing/placeholder PIXEL_SIZE_UM (=1.0) can never silently corrupt the geometry.
2. LOOSE COUPLING. No import of als_loader / datarecorder_loader. The caller adapts
   `als_loader.scanfields()` output (center/size/rotation/path-order) into ScanField
   dataclasses and passes them by value. Reads by argument, name references only.
3. SYNTHETIC VALIDATION IS A FIRST-CLASS GATE. `python als_raster_overlay.py` runs an
   analytic self-test (round-trip + known-geometry + rotated-raster + line-rotation) that
   must pass before any real `.scnnr.dat` / reference frame is touched.

Coordinate conventions
----------------------
- Reference coords: ScanImage scan-field reference space (any consistent unit; the loader's
  native scanfield units). Right-handed, +x right, +y "down the field".
- A ScanField maps field-local normalised coords u in [-0.5, 0.5]^2 to reference coords:
      p_ref = R(theta) @ (diag(w, h) @ u) + center,    R = CCW rotation by `rotation_deg`.
- Raster pixels: image[row, col]. With `y_down=True` (ScanImage image convention) local +y
  increases row downward. Pixel CENTRES: col = (u_x+0.5)*nx - 0.5, row = (u_y+0.5)*ny - 0.5.
- An ALS line is a degenerate field: endpoints = R(theta) @ (±length/2, 0) + center.

This file is dependency-light on purpose (numpy + matplotlib only); figstyle_tshino is used
if importable, otherwise an Okabe-Ito fallback keeps figures lab-consistent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np

# ---------------------------------------------------------------------------
# Okabe-Ito palette (figstyle_tshino lab standard; fallback if fs not present)
# ---------------------------------------------------------------------------
OKABE_ITO = {
    "black": "#000000", "orange": "#E69F00", "skyblue": "#56B4E9",
    "green": "#009E73", "yellow": "#F0E442", "blue": "#0072B2",
    "vermilion": "#D55E00", "purple": "#CC79A7",
}


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------
def _rot(theta_deg: float) -> np.ndarray:
    t = np.deg2rad(theta_deg)
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, -s], [s, c]], dtype=float)


@dataclass(frozen=True)
class ScanField:
    """A ScanImage scan field in reference coordinates.

    For an ALS *line*, set size=(length, 0.0); `path()` then returns the two endpoints.
    For a 2D field (e.g. an ROI box), size=(w, h) and `corners()` returns the rectangle.
    Build these from als_loader.scanfields() (center/size/rotation/path-order).
    """
    center: tuple[float, float]
    size: tuple[float, float]
    rotation_deg: float = 0.0
    name: str = ""
    order: int = 0  # ALS path order (which field is visited when)
    kind: str = "line"  # "line" = swept (carries data) | "pause"/"park" = dwell, no data

    @property
    def is_pause(self) -> bool:
        return self.kind in ("pause", "park")

    def entry_exit(self) -> tuple[np.ndarray, np.ndarray]:
        """(entry, exit) points in reference coords, in sweep direction (local +x).
        A pause/park is a single point (galvo parked) so entry == exit == center."""
        if self.is_pause:
            c = np.asarray(self.center, dtype=float)
            return c, c
        p = self.path(2)
        return p[0], p[-1]

    def local_to_ref(self, u: np.ndarray) -> np.ndarray:
        """u: (...,2) field-local normalised [-0.5,0.5] -> (...,2) reference coords."""
        u = np.asarray(u, dtype=float)
        scaled = u * np.asarray(self.size, dtype=float)
        return scaled @ _rot(self.rotation_deg).T + np.asarray(self.center, dtype=float)

    def path(self, n: int = 2) -> np.ndarray:
        """Sampled points along the line (local +x axis), reference coords, shape (n,2)."""
        s = np.linspace(-0.5, 0.5, n)
        u = np.column_stack([s, np.zeros_like(s)])
        return self.local_to_ref(u)

    def corners(self) -> np.ndarray:
        """Rectangle corners (closed, 5 pts) in reference coords."""
        u = np.array([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5], [-0.5, -0.5]])
        return self.local_to_ref(u)


@dataclass
class RasterFrame:
    """A raster reference image and the scan field it covers (same reference space).

    image: 2D array (ny, nx). scanfield: where the image sits in reference coords.
    pixel_size_um: µm per raster pixel (optional). Supplied ONLY to label axes / scale bar
    in µm; never required for registration. None => axes are in pixels (honestly labelled).
    """
    image: np.ndarray
    scanfield: ScanField
    pixel_size_um: Optional[float] = None
    y_down: bool = True

    def __post_init__(self) -> None:
        self.image = np.asarray(self.image)
        if self.image.ndim != 2:
            raise ValueError(f"raster image must be 2D, got shape {self.image.shape}")
        self.ny, self.nx = self.image.shape

    # -- reference <-> pixel affine (the heart of the registration) -----------
    def ref_to_pixel(self, p_ref: np.ndarray) -> np.ndarray:
        """(...,2) reference coords -> (...,2) pixel coords (col, row), pixel centres."""
        p_ref = np.asarray(p_ref, dtype=float)
        sf = self.scanfield
        local = (p_ref - np.asarray(sf.center)) @ _rot(sf.rotation_deg)  # R(-theta)=R^T applied on right
        u = local / np.asarray(sf.size, dtype=float)                    # normalised [-0.5,0.5]
        col = (u[..., 0] + 0.5) * self.nx - 0.5
        row = (u[..., 1] + 0.5) * self.ny - 0.5
        if not self.y_down:
            row = (self.ny - 1) - row
        return np.stack([col, row], axis=-1)

    def pixel_to_ref(self, p_px: np.ndarray) -> np.ndarray:
        """(...,2) pixel coords (col,row) -> (...,2) reference coords (inverse of above)."""
        p_px = np.asarray(p_px, dtype=float)
        col = p_px[..., 0]
        row = p_px[..., 1]
        if not self.y_down:
            row = (self.ny - 1) - row
        ux = (col + 0.5) / self.nx - 0.5
        uy = (row + 0.5) / self.ny - 0.5
        sf = self.scanfield
        local = np.stack([ux, uy], axis=-1) * np.asarray(sf.size, dtype=float)
        return local @ _rot(sf.rotation_deg).T + np.asarray(sf.center)

    def extent_for_imshow(self):
        """(left,right,bottom,top) for imshow. µm if pixel_size_um set, else pixel index."""
        if self.pixel_size_um is None:
            return (-0.5, self.nx - 0.5, self.ny - 0.5, -0.5)  # pixel space, row 0 at top
        w = self.nx * self.pixel_size_um
        h = self.ny * self.pixel_size_um
        return (0.0, w, h, 0.0)  # µm space, origin top-left

    def px_to_axis(self, p_px: np.ndarray) -> np.ndarray:
        """Map pixel coords into the axis units used by extent_for_imshow (px or µm)."""
        p_px = np.asarray(p_px, dtype=float)
        if self.pixel_size_um is None:
            return p_px
        return p_px * self.pixel_size_um


# ---------------------------------------------------------------------------
# Radial shells (Track-W (r,s) / systemic-water radial-shell readout bridge)
# ---------------------------------------------------------------------------
def radial_shells(center_ref: tuple[float, float], radii_ref: Sequence[float],
                  n: int = 180) -> list[np.ndarray]:
    """Concentric circles (reference coords) around a vessel centre, for the (r,s)
    shell apparatus. Returns a list of (n,2) ref-coord rings, one per radius.

    NOTE: this is the geometric substrate only. Assigning a shell as 'arteriole-side'
    vs 'venule-side' is downstream science that needs vessel-type ID + FOV calibration
    (pivot Phase 0). Drawn here so QC and the systemic-water readout share one tool.
    """
    th = np.linspace(0, 2 * np.pi, n)
    cx, cy = center_ref
    return [np.column_stack([cx + r * np.cos(th), cy + r * np.sin(th)]) for r in radii_ref]


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
def overlay(raster: RasterFrame,
            fields: Sequence[ScanField] = (),
            lines: Sequence[ScanField] = (),
            rois: Sequence[ScanField] = (),
            vessel_center_ref: Optional[tuple[float, float]] = None,
            shell_radii_ref: Optional[Sequence[float]] = None,
            ax=None, cmap: str = "gray", line_n: int = 50,
            show_path: bool = True, annotate_order: bool = True, title: str = ""):
    """Render the raster with the ALS scan PATH overlaid.

    `fields`: the ordered ROI-group path as returned by als_loader.scanfields() — a mix of
        swept lines (kind="line") and pause/park dwells (kind="pause"/"park"). Swept lines
        are drawn solid with endpoints; pauses are drawn as faint park markers (no data); the
        galvo travel between consecutive fields is drawn as a thin dotted connector when
        `show_path` is set, so the actual trajectory (line→pause→line…) is visible.
    `lines`/`rois`: convenience for the simple case (no pause structure); `lines` are treated
        as kind="line" if `fields` is empty.

    Returns (fig, ax). Units follow raster.extent_for_imshow (px today, µm once calibrated).
    """
    import matplotlib.pyplot as plt

    try:  # honour the lab figure standard if available
        import figstyle_tshino as fs  # noqa: F401  (presence => downstream can fs-convert)
    except Exception:
        fs = None

    if ax is None:
        fig, ax = plt.subplots(figsize=(5.2, 5.2))
    else:
        fig = ax.figure

    ax.imshow(raster.image, cmap=cmap, extent=raster.extent_for_imshow(),
              origin="upper", interpolation="nearest")

    palette = [OKABE_ITO["vermilion"], OKABE_ITO["blue"], OKABE_ITO["green"],
               OKABE_ITO["orange"], OKABE_ITO["purple"], OKABE_ITO["skyblue"]]

    def _axxy(ref_pts):
        return raster.px_to_axis(raster.ref_to_pixel(np.asarray(ref_pts)))

    # ROI boxes (2D fields) — drawn as light outlines.
    for i, roi in enumerate(rois):
        c = palette[i % len(palette)]
        xy = _axxy(roi.corners())
        ax.plot(xy[:, 0], xy[:, 1], "-", color=c, lw=1.0, alpha=0.9)

    # Resolve the ordered path: prefer `fields`; else fall back to `lines` as pure sweeps.
    path = list(fields) if fields else [ScanField(l.center, l.size, l.rotation_deg,
                                                  l.name, l.order, "line") for l in lines]
    path = sorted(path, key=lambda s: s.order)

    # Galvo travel between consecutive fields (exit_i -> entry_{i+1}): thin dotted gray.
    if show_path and len(path) >= 2:
        for a, b in zip(path[:-1], path[1:]):
            _, a_exit = a.entry_exit()
            b_entry, _ = b.entry_exit()
            seg = _axxy(np.vstack([a_exit, b_entry]))
            ax.plot(seg[:, 0], seg[:, 1], ":", color="0.55", lw=0.8, alpha=0.8, zorder=1)

    # Fields: swept lines solid+endpoints+label; pauses as faint park markers.
    li = 0
    for fld in path:
        if fld.is_pause:
            xy = _axxy(np.asarray(fld.center))
            ax.plot(xy[0], xy[1], marker="s", mfc="none", mec="0.5", ms=6, mew=1.2,
                    alpha=0.9, zorder=2)
            if annotate_order:
                ax.annotate(fld.name or "pause", xy, color="0.5", fontsize=7,
                            xytext=(4, -8), textcoords="offset points")
            continue
        c = palette[li % len(palette)]
        li += 1
        xy = _axxy(fld.path(line_n))
        ax.plot(xy[:, 0], xy[:, 1], "-", color=c, lw=2.0, alpha=0.95, zorder=3)
        ax.plot(xy[[0, -1], 0], xy[[0, -1], 1], "o", color=c, ms=4, alpha=0.95, zorder=3)
        if annotate_order:
            mid = xy[len(xy) // 2]
            lbl = fld.name or f"L{fld.order}"
            ax.annotate(lbl, mid, color=c, fontsize=8,
                        xytext=(4, 4), textcoords="offset points")

    if vessel_center_ref is not None and shell_radii_ref:
        for ring in radial_shells(vessel_center_ref, shell_radii_ref):
            xy = _axxy(ring)
            ax.plot(xy[:, 0], xy[:, 1], "--", color=OKABE_ITO["yellow"], lw=0.8, alpha=0.8)
        vxy = _axxy(np.asarray(vessel_center_ref))
        ax.plot(vxy[0], vxy[1], "+", color=OKABE_ITO["yellow"], ms=10, mew=2)

    unit = "µm" if raster.pixel_size_um is not None else "px"
    ax.set_xlabel(f"x ({unit})")
    ax.set_ylabel(f"y ({unit})")
    if raster.pixel_size_um is None:
        ax.text(0.02, 0.98, "uncalibrated (reference/pixel space)", transform=ax.transAxes,
                va="top", ha="left", fontsize=7, color=OKABE_ITO["vermilion"])
    if title:
        ax.set_title(title, fontsize=10)
    ax.set_aspect("equal")
    return fig, ax


# ---------------------------------------------------------------------------
# Synthetic validation gate (must pass before real data)
# ---------------------------------------------------------------------------
def _selftest() -> None:
    rng = np.random.default_rng(0)
    tol = 1e-9

    # (1) round-trip pixel<->reference identity, including a rotated raster.
    for phi in (0.0, 30.0, 345.0):
        rf = RasterFrame(np.zeros((512, 480)),
                         ScanField(center=(1.3, -2.1), size=(10.0, 9.0), rotation_deg=phi))
        px = rng.uniform(0, [rf.nx, rf.ny], size=(2000, 2))
        back = rf.ref_to_pixel(rf.pixel_to_ref(px))
        err = np.abs(back - px).max()
        assert err < 1e-6, f"round-trip phi={phi}: max|Δ|={err}"

    # (2) known geometry: centred raster, horizontal line, analytic pixel endpoints.
    rf = RasterFrame(np.zeros((512, 512)), ScanField(center=(0, 0), size=(10, 10)))
    line = ScanField(center=(0, 0), size=(5.0, 0.0), rotation_deg=0.0)
    ends = rf.ref_to_pixel(line.path(2))
    exp = np.array([[127.5, 255.5], [383.5, 255.5]])  # (col,row)
    err = np.abs(ends - exp).max()
    assert err < tol, f"known-geometry endpoints: max|Δ|={err}\n{ends}"

    # (3) line rotation 90° -> vertical in pixel space (col const, row spans).
    vline = ScanField(center=(0, 0), size=(5.0, 0.0), rotation_deg=90.0)
    e2 = rf.ref_to_pixel(vline.path(2))
    assert abs(e2[0, 0] - e2[1, 0]) < tol, "rot90 should keep col constant"
    assert abs(e2[0, 0] - 255.5) < tol, "rot90 col should be image centre"

    # (4) rotated raster composition: a line aligned with the raster's own +x axis must
    #     stay horizontal in pixel space regardless of the (shared) rotation phi.
    for phi in (15.0, 30.0, 345.0):
        rf2 = RasterFrame(np.zeros((300, 300)),
                          ScanField(center=(2, 3), size=(8, 8), rotation_deg=phi))
        ln = ScanField(center=(2, 3), size=(4.0, 0.0), rotation_deg=phi)
        e = rf2.ref_to_pixel(ln.path(2))
        assert abs(e[0, 1] - e[1, 1]) < 1e-6, f"raster-aligned line not horizontal @ phi={phi}"

    # (5) endpoint inside-frame sanity for a realistic multi-line layout (handoff rots).
    rf3 = RasterFrame(np.zeros((512, 512)), ScanField(center=(0, 0), size=(12, 12)))
    layout = [ScanField((-2, 1), (4.0, 0.0), 10.0, "ROI1", 0),
              ScanField((3, -2), (4.0, 0.0), 345.0, "ROI2", 1)]
    for ln in layout:
        e = rf3.ref_to_pixel(ln.path(2))
        assert (e >= -0.5).all() and (e[:, 0] <= rf3.nx - 0.5).all() \
            and (e[:, 1] <= rf3.ny - 0.5).all(), f"{ln.name} endpoints out of frame"

    # (6) pause/park entry_exit collapses to a point; line entry_exit are endpoints.
    pause = ScanField((1.0, -1.0), (0.0, 0.0), 0.0, "pause", 1, kind="pause")
    e_in, e_out = pause.entry_exit()
    assert np.allclose(e_in, e_out) and np.allclose(e_in, [1.0, -1.0]), "pause not a point"
    ln6 = ScanField((0, 0), (4.0, 0.0), 0.0, "L", 0)
    a, b = ln6.entry_exit()
    assert np.allclose(a, [-2, 0]) and np.allclose(b, [2, 0]), "line entry/exit wrong"

    print("[selftest] PASS — round-trip, known-geometry, line-rot, raster-rot, layout, pause")


def _demo_figure(path: str) -> None:
    """Render a synthetic ALS×raster overlay so the geometry is visually inspectable."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # synthetic vascular-ish raster: a diagonal "arteriole" + a "venule" as bright ridges.
    ny = nx = 512
    yy, xx = np.mgrid[0:ny, 0:nx].astype(float)
    img = np.zeros((ny, nx))
    # arteriole: line from (120,80) to (400,300)
    for t in np.linspace(0, 1, 600):
        cx, cy = 120 + t * 280, 80 + t * 220
        img += np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * 6.0 ** 2)))
    # venule: line from (380,120) to (140,420)
    for t in np.linspace(0, 1, 600):
        cx, cy = 380 - t * 240, 120 + t * 300
        img += 0.8 * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * 8.0 ** 2)))
    img += 0.04 * np.random.default_rng(1).standard_normal((ny, nx))

    rf = RasterFrame(img, ScanField(center=(0, 0), size=(10, 10)), pixel_size_um=None)
    # realistic ALS ROI-group path: line0 (swept) -> park (pause) -> line1 (swept).
    # scanfields() order is encoded in `order`; pause sits between the two sweeps.
    fields = [
        ScanField(center=(-0.5, -1.7), size=(3.0, 0.0), rotation_deg=38.0,
                  name="ALS L0", order=0, kind="line"),
        ScanField(center=(0.9, -0.2), size=(0.0, 0.0), rotation_deg=0.0,
                  name="park", order=1, kind="pause"),
        ScanField(center=(0.2, 1.6), size=(3.0, 0.0), rotation_deg=-51.0,
                  name="ALS L1", order=2, kind="line"),
    ]
    # radial shells around the arteriole crossing point (systemic-water (r,s) bridge)
    vessel_ref = rf.pixel_to_ref(np.array([260.0, 190.0]))
    fig, ax = overlay(rf, fields=fields, vessel_center_ref=tuple(vessel_ref),
                      shell_radii_ref=[0.6, 1.2, 1.8, 2.4], show_path=True,
                      title="Synthetic ALS×raster overlay — path line→pause→line (uncal.)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[demo] wrote {path}")


if __name__ == "__main__":
    _selftest()
    _demo_figure("als_raster_overlay_demo.png")
