"""
datarecorder_loader.py
----------------------
Reader + alignment helpers for ScanImage vDAQ Data Recorder HDF5 files.

Confirmed layout (2026-06-05 bench):
  - root group '/' attribute 'samplerate' (Hz), shared by all channels (single vDAQ clock)
  - one dataset per recorded signal, named by its "Recorded Name"
    (e.g. 'Legato130_TTL', 'frame_clock'), float32, extensible (MaxSize Inf), chunked
  - no explicit time vector  ->  t = sample_index / samplerate

This is the consumer side of the injector-t0 mechanism: given a Grab's Data
Recorder .h5 it yields the injection t0 (recorded TTL edge = analysis time-zero)
and the frame timebase (from frame_clock) -- the raw material for trigger_sync.

NOTE: reconcile naming/style with the existing toolkit (als_loader.py, etc.)
before committing into the repo. Metadata stays in sidecars, not filenames.
"""

from __future__ import annotations
import sys
import numpy as np
import h5py


def load_datarecorder(path):
    """Load a Data Recorder HDF5 into a dict.

    Returns dict with:
        'samplerate' : float Hz (root '/' attribute) or None
        'signals'    : {name: 1-D float64 ndarray}
        'names'      : list of dataset names
    """
    out = {"signals": {}, "names": [], "samplerate": None}
    with h5py.File(path, "r") as f:
        if "samplerate" in f.attrs:
            out["samplerate"] = float(np.squeeze(f.attrs["samplerate"]))
        for name in f.keys():
            out["signals"][name] = np.asarray(f[name][()]).ravel().astype(np.float64)
            out["names"].append(name)
    return out


def rising_edges(x, thresh=None):
    """Indices where x crosses upward through thresh.

    thresh=None -> midpoint of the signal's observed range (robust to 3.3 vs 5 V).
    Returns the index of the first sample at/above thresh for each crossing.
    """
    x = np.asarray(x, dtype=np.float64)
    if thresh is None:
        lo, hi = float(np.nanmin(x)), float(np.nanmax(x))
        if hi - lo < 1e-9:          # flat channel: no usable edges
            return np.array([], dtype=int)
        thresh = 0.5 * (lo + hi)
    return np.flatnonzero((x[:-1] < thresh) & (x[1:] >= thresh)) + 1


def injector_t0(data, ttl_name="Legato130_TTL", thresh=None):
    """(t0_seconds, edge_index, n_edges) for the injector TTL. t0 = edge/fs."""
    fs = data["samplerate"]
    edges = rising_edges(data["signals"][ttl_name], thresh)
    if edges.size == 0:
        return None, None, 0
    return edges[0] / fs, int(edges[0]), int(edges.size)


def frame_timebase(data, fc_name="frame_clock", thresh=None):
    """Frame timing from the frame_clock pulse train (one rising edge per frame).

    Frame rate is taken from the *median inter-frame interval*, NOT from
    n_frames / total_duration -- the recorder (Auto Start) runs a bit longer
    than the imaging, so dividing by total duration under-reports the true rate.
    head_pad/tail_pad quantify that offset (recorder-start is not frame-0; this
    is exactly why injection is anchored to frame_clock, not to t0).
    """
    fs = data["samplerate"]
    x = data["signals"][fc_name]
    edges = rising_edges(x, thresh)
    total_dur = x.size / fs
    if edges.size >= 2:
        rate = 1.0 / float(np.median(np.diff(edges) / fs))
        first_s, last_s = edges[0] / fs, edges[-1] / fs
    else:
        rate = float("nan")
        first_s = last_s = float("nan")
    return {
        "edges": edges,
        "n_frames": int(edges.size),
        "rate_hz": rate,
        "first_frame_s": first_s,
        "last_frame_s": last_s,
        "head_pad_s": first_s,                 # recorder start -> first frame
        "tail_pad_s": total_dur - last_s,      # last frame -> recorder stop
        "total_dur_s": total_dur,
    }


def summarize(path, ttl_name="Legato130_TTL", fc_name="frame_clock"):
    """Print the go/no-go numbers for one Grab's Data Recorder .h5."""
    data = load_datarecorder(path)
    fs = data["samplerate"]
    print(f"file        : {path}")
    print(f"samplerate  : {fs} Hz")
    print(f"datasets    : {data['names']}")

    inj_idx = None
    if ttl_name in data["signals"]:
        t0, inj_idx, n = injector_t0(data, ttl_name)
        if t0 is None:
            print(f"injector    : no rising edge in '{ttl_name}'")
        else:
            print(f"injector t0 : {t0:.4f} s  (sample {inj_idx}, {n} edge(s))")
    else:
        print(f"injector    : dataset '{ttl_name}' absent")

    if fc_name in data["signals"]:
        fb = frame_timebase(data, fc_name)
        print(f"frame_clock : {fb['n_frames']} frames, {fb['rate_hz']:.2f} Hz (median interval)")
        print(f"recorder    : {fb['total_dur_s']:.3f} s total | "
              f"head pad {fb['head_pad_s']:.3f} s, tail pad {fb['tail_pad_s']:.3f} s")
        if inj_idx is not None and fb["n_frames"]:
            k = int(np.sum(fb["edges"] < inj_idx))   # frames before the injection edge
            if 0 < k <= fb["edges"].size:
                dt = (inj_idx - fb["edges"][k - 1]) / fs
                print(f"inject      : frame {k} (+{dt*1000:.1f} ms into it), "
                      f"t0={inj_idx/fs:.4f} s (recorder-relative)")
            else:
                print(f"inject      : frame {k}")
    else:
        print(f"frame_clock : dataset '{fc_name}' absent (expected for ALS)")
    return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python datarecorder_loader.py <path.h5> [ttl_name] [frame_clock_name]")
        sys.exit(1)
    a = sys.argv[1:]
    kw = {}
    if len(a) >= 2:
        kw["ttl_name"] = a[1]
    if len(a) >= 3:
        kw["fc_name"] = a[2]
    summarize(a[0], **kw)
