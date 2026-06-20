# === C2 freeze: recorded_channels emitter (drop into make_trigger_sync.py) =========
# Method A: behavior (AI4/AI5) lives in the SAME Data Recorder .h5 as the injector
# (AI7) and clock (AI6), so the trigger_sync sidecar documents ALL channels. The old
# behavior_sidecar.schema.json / make_behavior_sidecar.py are method-B only -> DEPRECATE.
#
# MERGE STEPS in make_trigger_sync.py:
#   1) SCHEMA_VERSION = "0.3.0"            # was "0.2.0"
#   2) paste ROLE_MAP + recorded_channels() below
#   3) in the emitter, set:
#        chans, sr, n = recorded_channels(h5_path)
#        sidecar["schema_version"]   = SCHEMA_VERSION
#        sidecar["samplerate_hz"]    = sr
#        sidecar["n_samples"]        = n
#        sidecar["recorded_channels"]= chans
#   4) keep validating against trigger_sync.schema.json (now v0.3.0) before writing.

SCHEMA_VERSION = "0.3.0"

# name -> (physical AI, controlled-vocab role). ADDITIVE: add new channels here
# (e.g. "pupil_area": ("AI3", "pupil")) and extend the schema role enum to match.
ROLE_MAP = {
    "Legato130_TTL":   ("AI7", "injector_trigger"),
    "frame_clock":     ("AI6", "cycle_clock"),
    "treadmill_dir":   ("AI4", "locomotion_direction"),
    "treadmill_speed": ("AI5", "locomotion_speed"),
}


def recorded_channels(h5_path, role_map=ROLE_MAP):
    """Scan the Data Recorder .h5 -> (channels, samplerate_hz, n_samples).

    channels: [{name, ai, role, units:'V', range_v:[min,max]}] for every dataset.
    Fails LOUD on an unmapped channel (deliberate, like schema_version const) so a
    new stream can't silently slip past the contract -- add it to ROLE_MAP first.
    """
    import h5py
    import numpy as np

    chans, n = [], 0
    with h5py.File(h5_path, "r") as f:
        sr = f.attrs.get("samplerate", None)
        sr = float(sr) if sr is not None else None
        for name, dset in f.items():
            arr = np.asarray(dset[()], dtype=float)
            n = max(n, int(arr.size))
            if name not in role_map:
                raise ValueError(
                    f"unmapped recorded channel {name!r} in {h5_path}; "
                    f"add it to ROLE_MAP (and the schema role enum) before emitting.")
            ai, role = role_map[name]
            chans.append({
                "name": name,
                "ai": ai,
                "role": role,
                "units": "V",
                "range_v": [round(float(arr.min()), 6), round(float(arr.max()), 6)],
            })
    # deterministic order: sync first, then behavior, then name
    order = {"injector_trigger": 0, "cycle_clock": 1,
             "locomotion_speed": 2, "locomotion_direction": 3}
    chans.sort(key=lambda c: (order.get(c["role"], 9), c["name"]))
    return chans, sr, n
# ===================================================================================
