"""
diag_ttl.py -- characterize the injector TTL channel in a Data Recorder .h5.

Why: a clean single injection (delaySec/pulseSec) must give exactly ONE rising
edge. If als_inject_align reports many edges / a first edge at sample 1, AI7 is
recording the wrong thing (a free-running clock/WG, or noise/pickup). This tells
which.

Run from the acquisition repo's src/python (so 'import datarecorder_loader'
resolves as a sibling):

    python diag_ttl.py
    python diag_ttl.py <other.h5>            # reuse on a later grab
    python diag_ttl.py <other.h5> <signal>   # default signal = Legato130_TTL
"""

import sys
import numpy as np
import datarecorder_loader as DR

# --- edit this path (or pass it on the command line) ----------------------- #
DEFAULT_H5 = (
    r"D:\YasuiLab\workspace\2026_microscope_control_dev"
    r"\20260610_sub-ref_ses-01\sub-ref_ses-01_cond-qc_run-02_00001.h5"
)

p = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_H5
sig = sys.argv[2] if len(sys.argv) > 2 else "Legato130_TTL"

d = DR.load_datarecorder(p)
fs = d["samplerate"]
if sig not in d["signals"]:
    print(f"signal {sig!r} not in {d['names']}")
    sys.exit(1)
x = d["signals"][sig]

lo, hi = float(x.min()), float(x.max())
mid = 0.5 * (lo + hi)
print(f"file   : {p}")
print(f"signal : {sig}")
print(
    "n=%d dur=%.3fs  min=%.3f max=%.3f mean=%.3f  x0=%.3fV  frac_high=%.3f"
    % (
        x.size,
        x.size / fs,
        lo,
        hi,
        float(x.mean()),
        float(x[0]),
        float((x > mid).mean()),
    )
)

e = DR.rising_edges(x)  # auto threshold (midpoint)
e25 = DR.rising_edges(x, 2.5)  # fixed 2.5 V
print("edges_auto=%d  edges_at_2p5V=%d" % (e.size, e25.size))

if e.size > 1:
    di = np.diff(e) / fs
    print(
        "spacing: median=%.3fms (%.1fHz)  min=%.3fms  max=%.3fms  std=%.3fms"
        % (
            np.median(di) * 1e3,
            1.0 / np.median(di),
            di.min() * 1e3,
            di.max() * 1e3,
            di.std() * 1e3,
        )
    )
    print(
        "first10_edges_s =",
        np.round(e[:10] / fs, 4),
        " last_s =",
        round(float(e[-1]) / fs, 4),
    )

# longest sustained-HIGH region: does a real ~pulseSec pulse exist anywhere?
m = (x > mid).astype(np.int8)
dd = np.diff(np.r_[0, m, 0])
s0 = np.flatnonzero(dd == 1)
s1 = np.flatnonzero(dd == -1)
durs = (s1 - s0) / fs
if len(durs):
    j = int(np.argmax(durs))
    print(
        "high_segments=%d  longest=%.2fms (starts %.4fs)  shortest=%.3fms"
        % (len(durs), durs[j] * 1e3, s0[j] / fs, durs.min() * 1e3)
    )

# verdict
if e.size <= 1:
    print("VERDICT: single (or no) edge -> looks like a clean injector pulse.")
elif di.std() < 0.2 * np.median(di):
    print(
        "VERDICT: PERIODIC train ~%.0fHz -> AI7 carries a clock / free-running "
        "WG, not a single injection pulse." % (1.0 / np.median(di))
    )
else:
    print(
        "VERDICT: NON-periodic transitions -> noise/pickup, or a real pulse "
        "buried in noise (check the longest-segment line)."
    )
