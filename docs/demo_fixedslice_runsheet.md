# 実機 runsheet — fixed-slice demonstration ＋ rig closure（1 セッション）

```
last_updated:   2026-06-19
scope:          固定 CAG-EGFP 切片を phantom 代わりに、1 セッションで
                (1) demonstration データ取得（1Hz raster＋ALS 4-line 同 FOV・injector 決定論・behavior 同録）
                (2) rig closure（SI metadata SOP＝(A) 最後の契約ゲート／behavior を契約に／scnnr 末尾切れ／EMI 切り分け／4-line 確定）
                を同時に潰す。fixed＝可逆ゆえ不可逆判断不要。CNR phantom は後（別 runsheet）。
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（2026-06-19 reconciled）
related:        method_a_fixedframe_injection_runsheet.md（型）/ file_naming.md / nas_structure.md
                / status.md §2.1/§3.5 / vdaq_io_map.yaml / trigger_sync.schema.json
                / als_loader,datarecorder_loader,qc_core,qc_dashboard,sweep_quality,diag_ttl,make_sidecar,make_trigger_sync
report figures: F1 同期パネル / F2 ALS の中身 / F3 ALS vs 1Hz / F4 behavior EMI
```

> 状態の正本＝status.md / roadmap。本 doc は「実機で何を・どの順で・どこで go/no-go・何を閉じるか」だけ。

---

## 0. このセッションの PASS 定義（先に固定）

**demonstration（データ取得）**
- D1: 同一 FOV・同一 z で **1Hz galvo raster** 1 枚（参照像）＋ **ALS 4-line** を取得（fixed なので z は完全停止＝overlay が exact に効く）。
- D2: ALS grab で **injector 決定論（gate② config・着弾 cycle 既知）** ＋ **behavior（AI4/AI5）同録** が同一 HDF5・同一クロックに乗る。
- D3: `sweep_quality` PASS（毎 cycle 線を掃いている＝park 病でない）。

**rig closure（ride-along・別 grab を増やさない）**
- C1（=(A) 最後のゲート）: **SI 自動 metadata SOP 検証**＝gate 条件2 を閉じる（§4.1）。
- C2: **behavior を契約に**＝AI4/AI5 が同 HDF5・`datarecorder_loader` で同尺読み・schema の behavior ch 確定（§4.2）。
- C3: **scnnr 末尾切れ解消**＝pmt/clock/scnnr/commanded の cycle 数が ±1 で揃う（§4.3）。
- C4: **behavior EMI 切り分け**＝scanner ON/idle で behavior ノイズを比較し pickup か実信号か判定（§4.4）。
- C5: **4-line 取得が GUI Add バグ無く通る**ことを確定（ダメなら 3-line＋programmatic builder・blocker 扱いしない）。

> 上記が揃えば「実機側をある程度完全に締める」＝達成。CNR phantom（power 律速・Phase 3.2）は別 runsheet。

---

## 1. preflight（grab 前）

### 1.1 試料・命名・配置
- 試料: **固定 CAG-EGFP 切片**（aCSF/H2O 浸潤）。1 枚（option a・D2O 浸潤 pair は今回やらない）。
- dataset フォルダ: `<YYYYMMDD>_sub-ref_ses-01`（fixed なので `slice-01` でも可・parser permissive）。
- stem: **`sub-ref_ses-01_cond-qc_run-01`**（`cond-qc` の 1 語）。**fixed/slice/gfp/z はファイル名に入れない → metadata**（`sample.preparation=fixed`・`channels[].marker=gfp`・`acquisitions[].depth_um=z`）。`cagegfpfixed` 等の属性密輸は不可（file_naming 契約）。
- z を変える版は **`sub` で割らず depth_um で区別**（別視野にしたいなら `fov-` を使う）。
- 出力先は dataset の `raw/` 直下。

### 1.2 配線（vdaq_io_map と一致を目視）
- `D3.2`(injector DoTask 出力)→T→`AI7`(=t0 正本 `Legato130_TTL`)／`D2.1`(Aux・無害)／Legato 本体。
- `D0.0`(frame/cycle clock out)→T→`AI6`(`frame_clock` ループバック)＋`D2.2`(DoTask Start Trigger 入力)。
- `AI4=treadmill_dir`／`AI5=treadmill_speed`（behavior）。
- **WG 'TrigLegato130-2' を Resource Config で Remove**（D3.2 解放）してから DoTask を立てる。

### 1.3 ALS / 波形
- Optimize 不可（MBF 25850）→ **Reset Waveform → Calibrate + Test**。
- **Monitor Scanner Feedback ON**（`.scnnr.dat` 必須＝sweep_quality・overlay の真値）。
- ROI: **4-line**（in-vivo 想定配置・EGFP 構造を横切るように引く＝kymograph/profile が意味を持つ）。GUI Add バグが出たら §7。

### 1.4 Data Recorder（run-config）
- Sample Rate **5000 Hz**／Auto Start **ON**／Use Trigger **OFF**／Duration **Inf**／`hScan2D.logFramesPerFile=Inf`（**per-scanner**）。
- ch: `AI7→Legato130_TTL`・`AI6→frame_clock`・`AI4→treadmill_dir`・`AI5→treadmill_speed`。
- **末尾切れ対策（C3）**: grab 終了後すぐ Recorder を止めず、scan 末尾を覆う**余白**を残してから停止（head_pad 大の run で recorder 窓が scan 末尾 cyc を切るのを防ぐ）。

### 1.5 取得長
- `framesPerSlice`（ALS=cycle 数）を **`Inf`**（or 必要 cycle 数）。raster 切替時は再設定。

### 1.6 User Function（v4）
- `acqModeStart→syncArmStart`（DoTask 構成→start）／`acqAbort`・`acqDone→syncDisarm`／**`frameAcquired` 空**。
- N は `syncControlPanel`（`N=目標cycle−1`・+1 オフセットは表示吸収）。cycle period は hSI 自動（`scanFramePeriod`/`alsCyclePeriodS`）。
- **SI 起動中 `clear all`/`clear functions` 厳禁**。UF は Delete→再追加で fresh handle。

> **GO/NO-GO ①**: 1.1–1.6 を全確認 → GO。

---

## 2. 取得順（同一 FOV・stage 動かさない）

> idx（`_0000N`）は grab ごとに増える。run-01 のまま raster/ALS/EMI を別 idx で同居させてよい（file_naming）。grab 間差は metadata。

1. **1Hz galvo raster 参照**（`_00001`）: 同 FOV の reference 像。必要なら短 z-stack で plane を選ぶ（z は depth_um）。`logFramesPerFile`/`framesPerSlice` を raster 用に設定。
2. **ALS 4-line（本体）**（`_00002`）: 同 FOV・同 z に切替（mode 切替で 1.4/1.5 再設定）。
   - injector を **gate② config で arm**（N 設定→acqModeStart auto-arm）→ GRAB。injector は**同期の実証**（決定論 TTL を AI7 に記録）が目的で、固定切片への実注入は不要（パルスは waste/未接続で可）。
   - behavior（AI4/AI5）は Auto Start で同録。
3. **EMI 切り分け grab（C4）**（`_00003`〜）: 同 Recorder config で behavior を録りつつ、**scanner ON（通常 scan）** と **scanner idle/park（or beam block）** の 2 条件。behavior ノイズが scanner ON でのみ立つか比較。
4. 必要なら別 z で 1Hz/ALS を追加（depth_um 違い・idx 増）。

> **GO/NO-GO ②**: D1（同 FOV 1Hz＋ALS）取得済 → GO（QC へ）。

---

## 3. per-grab QC（取得直後・env `mcd-quicklook`）

ALS grab につき:
1. `diag_ttl.py` … AI7 **1 edge**（`edges@2.5V=1`）clean。
2. `qc_core.py <h5> <als_stem>`（or `qc_dashboard`）… injector 決定論（inject_cycle）・head_pad・cycle-count cross-check（pmt/scnnr/clock/commanded）・behavior 要約・sweep を 1 view で。
3. `sweep_quality.py <stem>.meta.txt` … per-cycle pp PASS（park 病でない＝D3）。
4. `datarecorder_loader.py <h5>` … behavior が同 HDF5・同 samplerate・同尺で読める（C2）。

> **GO/NO-GO ③**: diag_ttl 単発 ＋ inject_cycle 取得 ＋ sweep PASS ＋ cross-check ±1 → この grab 採用。欠ければ §7 で潰して取り直し。

---

## 4. ride-along closures

### 4.1 SI 自動 metadata SOP 検証（C1＝(A) 最後の契約ゲート・gate 条件2）
採用 grab の出力を file_naming / metadata_schema と突合:
- stem に**人間意図情報のみ**（sub/ses/cond/run）。scanner_type / scan_mode / parameters が**ファイル名に漏れていない**（→ metadata）。`_0000N` は仕様。
- ALS **3 ファイル**（`.meta.txt`/`.pmt.dat`/`.scnnr.dat`）が stem 共通で揃う。空 0KB `_00002` が出ていない（`logFramesPerFile=Inf` per-scanner）。
- SI 自動 metadata（`scanner_type=als` 等）が語彙と矛盾しない。**Ch 役割（Ch0/1/3=PMT2100 EGFP・Ch2=自作 PD/SRS）** が `channels[].name` と整合。
- Data Recorder HDF5: root attr `samplerate`／dataset 名＝Recorded Name／float32／time vector 無し。
- → 通れば **gate 条件2 PASS＝契約ゲート全開**。ズレは不可逆取得前に直す最後の窓（取得設定 or 契約 doc を直して再確認）。

### 4.2 behavior を契約に（C2）
- AI4/AI5 が同 HDF5・同 clock。`datarecorder_loader` で同尺読み。`trigger_sync.schema.json` の behavior ch（name/role/range_v）を実測で確定。range_v を記録。

### 4.3 scnnr 末尾切れ（C3）
- `qc_core` の cycle-count cross-check で pmt/scnnr/clock/commanded が **±1 で揃う**か。揃わなければ 1.4 の recorder 余白を増やして再取得（コマ落ちでなく recorder 窓の問題）。先頭/末尾どちらが欠けるかも記録（overlay/F3 の前提）。

### 4.4 behavior EMI 切り分け（C4）
- §2-3 の scanner ON vs idle で behavior ノイズを比較。ON のみで立つ → **scanner EMI pickup**（in-vivo behavior 解釈時に要対策）。idle でも立つ → 別要因。判定を notes に記録。

### 4.5 4-line 確定（C5）
- 4-line が GUI Add バグ無く取得できたか。出れば確定。出なければ §7（3-line＋programmatic builder で代替・blocker 扱いしない）。

---

## 5. 各 figure がこのセッションから得るもの

- **F1 同期パネル**: ALS grab（§2-2）の h5 → ALS cycle clock＋injector 決定論 inject_cycle＋behavior を 1 タイムベース。`qc_core` ベースで report 品質に。（既存 gate② run でも先行可。）
- **F2 ALS の中身**: ALS 4-line（§2-2）→ kymograph（cycle×位置）／per-line profile／`feedback_on_pmt_grid` の scanner 軌跡。
- **F3 ALS vs 1Hz**: 1Hz raster（§2-1）＋ALS scanfields（`als_loader.scanfields()`）→ overlay（ALS line を 1Hz 像に重畳）＋並置比較。同 FOV・同 z ゆえ overlay は exact（C3 で scnnr 整合確認済）。
- **F4 EMI**: §2-3 の scanner ON/idle behavior 比較。

---

## 6. post（offload・metadata・doc 更新）

- **offload**: 実機 → takan（local）→ NAS。robocopy（增分・`/E /R:2 /W:5 /MT:16 /XO`・`/MIR` 不使用）で `Y:\projects\2026_microscope_control_dev\<modality>\<dataset_id>\raw\` へ。検証再走 `Copied:0`。modality はこの dataset を **1 つ**に（option a は `2photon`・channels は metadata）。
- **metadata**: NAS raw/ で dataset `metadata.yaml`（generate_metadata＋手書き: subject=ref/sample(fixed,gfp,region)/channels[].name/depth_um/acquisition_type）＋per-acq sidecar（ALS=`make_sidecar`・sync=`make_trigger_sync`）。全部 raw/ に co-locate。
- **HDD copy #3**（任意・後日）: NAS→`L:` 增分・offline 保管。
- **doc 更新**: status.md §2.1（gate 条件2 ☑）・roadmap §5 gate2 ミラー・新 handoff。**modification は継続**。

---

## 7. トラブルシュート

- **AI7 flat（edges=0）**: DoTask 未 arm／WG 未 Remove。→ 1.2・1.6。
- **AI7 長 HIGH**: continuous のまま。→ finite（v4 既定 finite）。
- **inject_cycle ばらつく**: D2.2 trigger source／D0.0→D2.2 T 分岐／branch A clock loopback を確認。
- **4-line GUI Add バグ**（`ArbitraryLineScanRoiGui>addRoi`）: SI 再起動／保存 ROI ロード／2-line 複製／**programmatic builder**（用意済）。再現なら MBF 報告（Optimize Waveform 25850 と束ねる）。3-line で代替可（機構は line 数非依存）。
- **scnnr が pmt/clock より短い**: recorder 末尾余白を増やす（1.4）。コマ落ちでない。
- **「must write buffer」/ DoTask 罠**: `sampleMode='finite'` 明示・`sampleRate` property 直叩き（`cfgSampClkTiming` 不可）・`convertToBufferedTask` 必須（status §3.5）。
