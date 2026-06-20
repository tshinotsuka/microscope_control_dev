# In-vivo acquisition shakedown — runsheet

**Goal:** prove the *exact* demo pipeline (1 Hz raster ref + sustained ALS +
fixed-frame injector + 4-ch behavior + contract sidecar + QC chain) runs
end-to-end on a **head-fixed live mouse**. This is an acquisition / mechanics
shakedown, not a biology experiment.

Supersedes nothing; sibling of `demo_fixedslice_runsheet.md` (now with an animal).

---

## 0. Scope & non-goals — READ FIRST

**In scope (reversible de-risk):**
- Same 2-mode scope as the demo: galvo 1 Hz raster + ALS, frame-clock anchored.
- Injector fires deterministically at **cycle #501** with **saline / vehicle**
  (or a dry trigger with no infusion). The point is the *timing mechanism on a
  live prep*, not the tracer.
- Behavior (treadmill_dir/speed) recorded in the same Data Recorder HDF5.
- Contract sidecar emitted + validated (v0.3.0), QC chain run per grab.

**Explicitly OUT of scope — do NOT collapse these in (separate later, gated phase):**
- Systemic **D2O** dosing, plasma-tracer kinetics.
- Awake / vasomotion-intact protocol, vessel-type ID.
- **fast-SRS power–SNR determination (Phase 3.2)** — needs in-vivo perfusion;
  it is its own gate *after* this shakedown.

> Rationale: the systemic-D2O / awake / SRS-power conditions are irreversible (C)
> prerequisites. A shakedown must not consume them. Inject saline, keep it
> repeatable, throw the animal-day away if needed.

---

## 1. Preflight — go/no-go gates

Do these IN ORDER. A red gate stops the session.

### G1 — C1 pixel size (CARRIED PENDING from 2026-06-20)
- [ ] In ScanImage, set **`objectiveResolution`** to the **calibrated** value
      (graticule: `objectiveResolution = measured_FOV_um / scan_angle_deg`;
      back-of-envelope target ~34.4 for FOV 465 µm @ 13.5°).
  - If it still reads 15 after editing: SI is loading a *different* MDF, or a
    soft reload — confirm the active config/MDF path shown at SI startup, edit
    THAT, and **fully restart SI**. Premium 2026 may hold it per-objective in the
    Objectives manager rather than a bare MDF scalar.
- [ ] Acquire a 1 Hz raster, then verify:
  ```powershell
  python dump_si_metadata.py "<raster>_00001.tif" --json c1_ref_raster.json
  python -c "import json; d=json.load(open('c1_ref_raster.json')); u=d['imaging_scanfields'][0]['um_per_px_xcheck'][0]; o=d['checks']['objectiveResolution']['value']; print(f'objRes={o} um/px={u:.4f} FOV={u*512:.1f}um'); print('C1 PASS' if abs(u-0.908)<0.05 else 'C1 FAIL')"
  ```
  **GO when:** `C1 PASS`, FOV ≈ 465 µm. Freeze `c1_ref_raster.json` into the
  contract; switch figures from `--px-per-um 1.1` to metadata-derived.
  **If FAIL:** keep `--px-per-um 1.1` for this session's data and flag it
  (pixel size provisional); do not block the shakedown on it.

### G2 — C4 EMI floor (NO animal)
- [ ] Record **scanner-OFF** (galvo parked) and **scan-ON ALS, no animal** .h5.
- [ ] Quantify treadmill RMS in idle vs scan window (+ FFT for scan-locked peaks).
- **GO when:** you KNOW the EMI floor amplitude and whether expected locomotion
  rises above it. If EMI dominates, behavior is provisional this session —
  acquisition still proceeds, behavior interpretation is gated downstream.
- (Mitigation if pursued: shield/twist/differential the encoder lines, star-GND,
  route away from galvo drivers; or notch the scan-synchronous EMI.)

### G3 — sync / injector arm
- [ ] `framesPerSlice = Inf` for the ALS sustained grab (Gate①).
- [ ] DoTask injector on **D3.2**, trig **D2.2** (frame-clock), ~150 ms pulse.
- [ ] **Dry-fire**: confirm a single clean injector pulse, `n_edges = 1`,
      lands at **cycle #501** before touching the animal.
- [ ] `WaveformGenerator 'TrigLegato130-2'` Removed (D3.2 free).

### G4 — fluidics
- [ ] Legato130 loaded with **saline / vehicle**, tubing primed, no air.
- [ ] Note tube dead-volume + pump rise (stays as `physical_delay_offset_s = null`
      until separately calibrated — do NOT fold into t0).

### G5 — animal (head-fixed)
- [ ] Habituated / headplate clamp seated, treadmill free-spins.
- [ ] Objective coupling (water/immersion), window clean, depth set.
- [ ] Eye protection; ASR/anesthesia state per protocol.

### G6 — disk / naming
- [ ] Dataset: `<modality>/<YYYYMMDD>_sub-XX_ses-YY/raw/`
      (modality folder UPPERCASE for SRS; `2photon` for 2PE).
- [ ] Naming: `sub-XX_ses-YY_cond-<c>_run-<NN>_NNNNN`.
- [ ] Recorder **Auto-Start ON**; plan to **stop 2–3 s after grab end** (C3 margin —
      avoids the scnnr/recorder tail clip).

---

## 2. Acquisition order (per run)

1. **1 Hz raster reference** (`_00001`) — anatomy + pixel-size anchor.
   - First run only: re-run the G1 dump verify on this raster (confirms the rig
     state, not just a stale file).
2. **Sustained ALS grab** (`_0000X`) — recorder Auto-Start → scan start →
   injector auto-fires at cycle #501 → let it run → **stop recorder 2–3 s after
   the grab**. Behavior records in the same HDF5.
3. Repeat (2) for N runs. New raster ref if the field moved.

---

## 3. Per-grab QC (at rig, `mcd-quicklook`)

QC chain (PMT cycle count from file size, never load the 160 MB pmt.dat):
```
diag_ttl.py        -> single clean injector edge, n_edges = 1
als_inject_align.py-> inject_cycle = 501, head_pad measured, n_cycles ≈ commanded
sweep_quality.py   -> pp flat / PASS
```
Emit + validate the contract sidecar (v0.3.0; recorded_channels auto-includes
behavior; als_datafile stored as basename):
```powershell
python make_trigger_sync.py "<grab>.h5" als --als-datafile "<grab>" --n-cycles-commanded <N> --schema ..\..\schemas\trigger_sync.schema.json
```
**Expect:** `[validate] OK`, `inject_cycle 501`, `n_cycles = N`, 4 recorded_channels.

Eyeball figures (analysis side, `ivwib`): F1 `fig_sync_panel`, F2 `fig_als_content`,
F3 `fig_als_raster_overlay`. **Until G1 PASS this session, pass `--px-per-um 1.1`.**

---

## 4. Known issues carried in

- **C1 pixel size** — provisional until G1 PASS on this rig state.
- **Behavior EMI** — scan-correlated (G2); treat locomotion as provisional until
  the floor is characterized/mitigated. No-animal baseline lives in preflight.
- **physical_delay_offset_s = null** — tube/pump delay uncalibrated; applied
  downstream only, never folded into t0.
- **scnnr tail clip** — benign; recorder 2–3 s margin (C3) is the mitigation.

---

## 5. Offload (NAS currently unavailable)

Rig (NAS-disconnected by design) → **takan** (USB / network) → NAS when access
returns. Additive robocopy, single-line PowerShell (backtick continuation, never
`^`), `/E /XO`, no `/MIR`. HDD `L:` = copy #3 (3-2-1), additive only, normally
disconnected.

---

## 6. Abort / troubleshoot

| symptom | likely cause | action |
|---|---|---|
| inject not at #501 | DoTask N≠500, or arm missed | re-arm, dry-fire, recheck N=target−1 |
| no frame_clock cycles | D0.0→AI6 loopback / single-frame ref | expected on the raster ref; ALS grab must show 125 Hz |
| behavior = pure EMI | scanner pickup (G2) | flag behavior provisional; continue acquisition |
| recorder tail clip | stopped too early | stop 2–3 s after grab |
| objectiveResolution = 15 | MDF not applied | fix per G1 note, full SI restart |

---

## After the shakedown

Once a run cleanly passes §3 with an animal in place, the acquisition contract is
demonstrated in-vivo. **Next gated phase (separate runsheet):** SRS SNR / fast-SRS
power determination (Phase 3.2) and the systemic-D2O science protocol — none of
which this shakedown consumes.
