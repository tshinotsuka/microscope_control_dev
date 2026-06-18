[sync] armed DoTask on D3.2 (finite), trig /vDAQ0/D2.2/rising, target cycle N=500 (R=100000 Hz, nSamp=420000, ~4.000s delay)

[sync] disarmed DoTask (line LOW)

[sync] disarm: no live DoTask (already clean)

[sync] armed DoTask on D3.2 (finite), trig /vDAQ0/D2.2/rising, target cycle N=500 (R=100000 Hz, nSamp=420000, ~4.000s delay)

[sync] disarmed DoTask (line LOW)

[sync] disarm: no live DoTask (already clean)

>>



(mcd-quicklook) PS C:\Users\KeioPharmMicroscopy2\Shinotsuka\GitHub\microscope_control_dev> python  src\python\diag_ttl.py "D:\Shinotsuka\data\2026_microscope_control_dev\20260618_sub-ref_ses-01\sub-ref_ses-01_cond-qc_run-01_00003.h5"                                                                                     

file   : D:\Shinotsuka\data\2026_microscope_control_dev\20260618_sub-ref_ses-01\sub-ref_ses-01_cond-qc_run-01_00003.h5

signal : Legato130_TTL

n=49664 dur=9.933s  min=-0.006 max=5.081 mean=0.076  x0=0.000V  frac_high=0.015

edges_auto=1  edges_at_2p5V=1

high_segments=1  longest=150.00ms (starts 5.9838s)  shortest=150.000ms

VERDICT: single (or no) edge -> looks like a clean injector pulse.

(mcd-quicklook) PS C:\Users\KeioPharmMicroscopy2\Shinotsuka\GitHub\microscope_control_dev> python src\python\als_inject_align.py "D:\Shinotsuka\data\2026_microscope_control_dev\20260618_sub-ref_ses-01\sub-ref_ses-01_cond-qc_run-01_00003.h5" "D:\Shinotsuka\data\2026_microscope_control_dev\20260618_sub-ref_ses-01\sub-ref_ses-01_cond-qc_run-01_00003"

recorder    : sub-ref_ses-01_cond-qc_run-01_00003.h5  (9.9328 s @ 5000 Hz)

als         : sub-ref_ses-01_cond-qc_run-01_00003  cycle 8.0 ms (125.0 Hz), 1000 cyc x 4 line = 8.0 s

injector t0 : 5.9838 s (sample 29919, 1 edge) recorder-relative

branch      : A_clock   anchor=als_datafile_timing

clock       : 'frame_clock' cycle @ 125.0 Hz, 994/1000 edges  [CHECK]

RESIDUAL    : 1.9838 s   <-- ALS head_pad (go/no-go 3)

inject map  : cycle #501 (+0.2 ms) -> pmt sample 500, in ROI 2 (pause)

  ! clock edge count does not match meta cycle/line count (±1).

(mcd-quicklook) PS C:\Users\KeioPharmMicroscopy2\Shinotsuka\GitHub\microscope_control_dev> python  src\python\diag_ttl.py "D:\Shinotsuka\data\2026_microscope_control_dev\20260618_sub-ref_ses-01\sub-ref_ses-01_cond-qc_run-01_00004.h5"                                                                                     

file   : D:\Shinotsuka\data\2026_microscope_control_dev\20260618_sub-ref_ses-01\sub-ref_ses-01_cond-qc_run-01_00004.h5

signal : Legato130_TTL

n=45824 dur=9.165s  min=-0.006 max=5.079 mean=0.083  x0=0.000V  frac_high=0.016

edges_auto=1  edges_at_2p5V=1

high_segments=1  longest=150.00ms (starts 5.1556s)  shortest=150.000ms

VERDICT: single (or no) edge -> looks like a clean injector pulse.

(mcd-quicklook) PS C:\Users\KeioPharmMicroscopy2\Shinotsuka\GitHub\microscope_control_dev> python src\python\als_inject_align.py "D:\Shinotsuka\data\2026_microscope_control_dev\20260618_sub-ref_ses-01\sub-ref_ses-01_cond-qc_run-01_00004.h5" "D:\Shinotsuka\data\2026_microscope_control_dev\20260618_sub-ref_ses-01\sub-ref_ses-01_cond-qc_run-01_00004"

recorder    : sub-ref_ses-01_cond-qc_run-01_00004.h5  (9.1648 s @ 5000 Hz)

als         : sub-ref_ses-01_cond-qc_run-01_00004  cycle 8.0 ms (125.0 Hz), 1000 cyc x 4 line = 8.0 s

injector t0 : 5.1556 s (sample 25778, 1 edge) recorder-relative

branch      : A_clock   anchor=als_datafile_timing

clock       : 'frame_clock' cycle @ 125.0 Hz, 1000/1000 edges  [OK]

RESIDUAL    : 1.1554 s   <-- ALS head_pad (go/no-go 3)

inject map  : cycle #501 (+0.0 ms) -> pmt sample 0, in ROI 2 (pause)

(mcd-quicklook) PS C:\Users\KeioPharmMicroscopy2\Shinotsuka\GitHub\microscope_control_dev>



2 runの結果。いいんじゃない?