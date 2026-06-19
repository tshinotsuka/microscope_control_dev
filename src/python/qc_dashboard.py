"""
qc_dashboard.py -- Layer-2 .h5 QC dashboard (PyQtGraph) over qc_core.

One file selection folds the per-grab diag_ttl -> als_inject_align -> sweep_quality
hand-run into a single view:
    * injector TTL waveform + t0 marker + single/periodic/noisy verdict
    * clock (cycle/frame) + inject marker + head_pad band
    * behavior traces (treadmill_dir / speed / ...)
    * ALS sweep per-cycle peak-to-peak + PASS/CHECK
    * cross-stream cycle-count check (pmt / scnnr / clock / commanded)
mode-general (galvo frame / ALS cycle), so resonant reuses it unchanged.

Data layer = qc_core.qc_load (scalars/verdicts, contract-consistent) + the raw
recorder signals for the traces. Offline tool (ivwib / mcd-quicklook env); no SI
internals. The Qt-free prep functions (derive_als_stem / panels_data /
overall_status) are unit-testable without a display.

Run:
    python qc_dashboard.py [recorder.h5]
Deps: pyqtgraph (+ a Qt binding: PyQt5/PySide2/PyQt6/PySide6), numpy, h5py.
"""
from __future__ import annotations

import os
import sys

import numpy as np

import datarecorder_loader as DR
import qc_core


# --------------------------------------------------------------------------- #
# data prep (Qt-free; unit-testable)
# --------------------------------------------------------------------------- #
def derive_als_stem(h5_path):
    """ALS stem if the sibling .meta.txt exists (-> ALS mode), else None (galvo)."""
    stem = h5_path[:-3] if h5_path.lower().endswith(".h5") else os.path.splitext(h5_path)[0]
    return stem if os.path.exists(stem + ".meta.txt") else None


def _first_len(data):
    for n in data["names"]:
        return data["signals"][n].size
    return 0


def panels_data(h5_path, ttl_name="Legato130_TTL", clock_name="frame_clock"):
    """Everything the dashboard renders, as plain arrays/dicts (no Qt)."""
    als_stem = derive_als_stem(h5_path)
    qc = qc_core.qc_load(h5_path, als_stem, ttl_name=ttl_name, clock_name=clock_name)

    data = DR.load_datarecorder(h5_path)
    fs = data["samplerate"] or 1.0
    t = np.arange(_first_len(data)) / fs
    traces = {"t": t, "ttl": None, "clock": None, "behavior": {}}
    if ttl_name in data["signals"]:
        traces["ttl"] = data["signals"][ttl_name]
    if clock_name in data["signals"]:
        traces["clock"] = data["signals"][clock_name]
    for name in data["names"]:
        if name not in (ttl_name, clock_name):
            traces["behavior"][name] = data["signals"][name]

    # ALS sweep pp (scnnr only; never reads the big .pmt.dat)
    pp = None
    if als_stem is not None:
        try:
            import als_loader as AL
            ls = AL.load(als_stem, read_data=False)
            scn_path = ls.stem + ".scnnr.dat"
            if ls.info.record_feedback and os.path.exists(scn_path):
                pp = qc_core._per_cycle_pp(AL.load_scnnr(scn_path, ls.info))
        except Exception:                       # noqa: BLE001 (plot is best-effort)
            pp = None

    return {"qc": qc, "fs": fs, "traces": traces, "pp": pp, "als_stem": als_stem}


def overall_status(qc):
    """(ok_bool, summary_str). ok = injector single edge + sweep PASS/(n.a.) + no cycle mismatch."""
    issues = []
    inj = qc.get("injector")
    if not (inj and inj.get("sample_index") is not None):
        issues.append("no injector edge")
    elif inj["verdict"] != "single":
        issues.append(f"injector {inj['verdict']}")
    sw = qc.get("sweep")
    if sw and sw["verdict"] != "PASS":
        issues.append("sweep CHECK")
    cc = qc.get("cycle_counts")
    if cc and (max(cc.values()) - min(cc.values()) > 1):
        issues.append("cycle-count mismatch")
    return (len(issues) == 0), ("all checks pass" if not issues else "; ".join(issues))


# --------------------------------------------------------------------------- #
# Qt dashboard
# --------------------------------------------------------------------------- #
def launch(h5_path=None):
    import pyqtgraph as pg
    from pyqtgraph.Qt import QtWidgets

    pg.setConfigOptions(antialias=True, background="w", foreground="k")
    GREY = "#888888"

    class QCWindow(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("ALS / galvo  .h5 QC")
            self.resize(1100, 880)
            central = QtWidgets.QWidget()
            self.setCentralWidget(central)
            v = QtWidgets.QVBoxLayout(central)

            # top bar: open / file / status LED / summary
            top = QtWidgets.QHBoxLayout()
            self.btnOpen = QtWidgets.QPushButton("Open .h5…")
            self.btnOpen.clicked.connect(self.on_open)
            self.lblFile = QtWidgets.QLabel("(no file)")
            self.led = QtWidgets.QLabel("\u25CF")
            self.led.setStyleSheet("color:#999; font-size:20px")
            self.lblSummary = QtWidgets.QLabel("")
            self.lblSummary.setStyleSheet("font-weight:bold")
            top.addWidget(self.btnOpen)
            top.addWidget(self.lblFile, 1)
            top.addWidget(self.led)
            top.addWidget(self.lblSummary)
            v.addLayout(top)

            # stacked plots
            self.glw = pg.GraphicsLayoutWidget()
            v.addWidget(self.glw, 1)
            self.pInj = self.glw.addPlot(row=0, col=0, title="injector TTL")
            self.pClk = self.glw.addPlot(row=1, col=0, title="clock + inject")
            self.pBeh = self.glw.addPlot(row=2, col=0, title="behavior")
            self.pSwp = self.glw.addPlot(row=3, col=0, title="ALS sweep (per-cycle pp)")
            for p in (self.pInj, self.pClk, self.pBeh):
                p.setDownsampling(auto=True)
                p.setClipToView(True)
                p.showGrid(x=True, y=True, alpha=0.2)
            self.pClk.setXLink(self.pInj)
            self.pBeh.setXLink(self.pInj)
            self.pBeh.setLabel("bottom", "t (s, recorder-relative)")
            self.pSwp.setLabel("bottom", "cycle")
            self.pSwp.setLabel("left", "pp (2D)")
            self.pSwp.showGrid(x=True, y=True, alpha=0.2)
            self.behLegend = self.pBeh.addLegend(offset=(-10, 10))

            # warnings / cross-check
            self.txt = QtWidgets.QPlainTextEdit()
            self.txt.setReadOnly(True)
            self.txt.setMaximumHeight(130)
            self.txt.setStyleSheet("font-family:monospace; font-size:11px")
            v.addWidget(self.txt)

        # ---- actions ----
        def on_open(self):
            fn, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Open Data Recorder .h5", "", "HDF5 (*.h5)")
            if fn:
                self.load(fn)

        def load(self, h5_path):
            self.lblFile.setText(h5_path)
            try:
                D = panels_data(h5_path)
            except Exception as e:               # noqa: BLE001
                self.txt.setPlainText(f"load failed: {type(e).__name__}: {e}")
                self.led.setStyleSheet("color:#d62728; font-size:20px")
                self.lblSummary.setText("load failed")
                return
            self.render(D)

        # ---- render ----
        def render(self, D):
            qc, fs, tr, pp = D["qc"], D["fs"], D["traces"], D["pp"]
            t = tr["t"]
            for p in (self.pInj, self.pClk, self.pBeh, self.pSwp):
                p.clear()
            self.behLegend.clear()

            inj = qc.get("injector")
            x0 = (inj["sample_index"] / fs) if (inj and inj.get("sample_index") is not None) else None

            # injector TTL
            if tr["ttl"] is not None:
                self.pInj.plot(t, tr["ttl"], pen=pg.mkPen("#1f77b4"))
            if x0 is not None:
                self.pInj.addItem(pg.InfiniteLine(x0, pen=pg.mkPen("#d62728", width=2)))
            if inj:
                self.pInj.setTitle(f"injector TTL \u2014 t0={inj['t0_recorder_s']} s, "
                                   f"edges={inj['n_edges']}  [{inj['verdict']}]")

            # clock + inject + head_pad band
            tm = qc.get("timing")
            if tr["clock"] is not None:
                self.pClk.plot(t, tr["clock"], pen=pg.mkPen("#2ca02c"))
            if tm and tm.get("head_pad_s"):
                band = pg.LinearRegionItem([0.0, tm["head_pad_s"]], movable=False,
                                           brush=pg.mkBrush(255, 200, 0, 45))
                band.setZValue(-10)
                self.pClk.addItem(band)
            if x0 is not None:
                self.pClk.addItem(pg.InfiniteLine(x0, pen=pg.mkPen("#d62728", width=2)))
            if tm:
                lbl = "cycle" if tm["mode"] == "als" else "frame"
                nc = f"/{tm['n_commanded']}" if tm.get("n_commanded") else ""
                self.pClk.setTitle(
                    f"clock+inject \u2014 {tm['mode']} {tm['n']}{nc}@{tm['rate_hz']}Hz, "
                    f"head_pad={tm['head_pad_s']}s, inject@{lbl} #{tm['inject_index_1based']} "
                    f"(+{tm['inject_offset_ms']}ms)")

            # behavior
            names = list(tr["behavior"].keys())
            for i, name in enumerate(names):
                self.pBeh.plot(t, tr["behavior"][name],
                               pen=pg.intColor(i, hues=max(len(names), 1)), name=name)
            if not names:
                self.pBeh.setTitle("behavior (none recorded)")
            else:
                self.pBeh.setTitle("behavior")

            # ALS sweep
            if pp is not None and pp.size:
                self.pSwp.plot(np.arange(pp.size), pp, pen=pg.mkPen("#9467bd"))
                sw = qc.get("sweep")
                if sw:
                    p05, p50 = sw["pp_percentiles"][1], sw["pp_percentiles"][3]
                    self.pSwp.addItem(pg.InfiniteLine(p50, angle=0, pen=pg.mkPen(GREY, width=1)))
                    self.pSwp.addItem(pg.InfiniteLine(p05, angle=0, pen=pg.mkPen(GREY, width=1)))
                    self.pSwp.setTitle(f"ALS sweep \u2014 {sw['n_cycles']} cyc, "
                                       f"median/5th={sw['median_over_5th']}  [{sw['verdict']}]")
            else:
                self.pSwp.setTitle("ALS sweep (n/a \u2014 galvo or no feedback)")

            # status + warnings
            ok, summ = overall_status(qc)
            self.led.setStyleSheet(f"color:{'#2ca02c' if ok else '#d62728'}; font-size:20px")
            self.lblSummary.setText(summ)
            lines = []
            if qc.get("cycle_counts"):
                lines.append("cycle_counts: " + str(qc["cycle_counts"]))
            for w in qc.get("warnings", []):
                lines.append("! " + w)
            self.txt.setPlainText("\n".join(lines) if lines else "no warnings")

    app = pg.mkQApp("ALS / galvo .h5 QC")
    win = QCWindow()
    win.show()
    if h5_path:
        win.load(h5_path)
    pg.exec()


if __name__ == "__main__":
    launch(sys.argv[1] if len(sys.argv) > 1 else None)
