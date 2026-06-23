# Status — 取得側（microscope_control_dev）ベンチ進捗

```
更新方法:   この 1 ファイルを in-place 更新（dated にしない）。取得系ベンチ進捗の正本＝これ。

priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）

scope:      Tier 順・各モダリティの実装状態・次手。設計の正は sync_architecture.md（loose coupling）。

related:    sync_architecture.md / vdaq_io_map.yaml / strategy_roadmap.md / scanimage_vdaq_internals.md

/ trigger_sync.schema.json / in_vivo_migration_runsheet.md

/ datarecorder_loader.py / als_loader.py / als_inject_align.py / diag_ttl.py / sweep_quality.py

/ make_trigger_sync.py / dump_si_metadata.py / emi_quant.py / qc_core.py / qc_dashboard.py

注:         現行版＝galvo go＋ALS go（single+multi-line/4-line）／本番前ハードウェアゲート①②=closed／

injector を DoTask frame-trigger 化（WG 廃止）／契約ゲート C1-C4 closed＝(A) engineering ゲート完全クローズ。
```

---

## 1. 現在地（2026-06-23）

**(A) engineering ゲート完全クローズ＝契約全開。** 残っていた C1（pixel size・SI 自動 metadata 実機 SOP）を両対物で graticule 確定し、前回 pending（objectiveResolution=15 サイレント復帰）を root cause から解明・SOP 化。①②R1C2C3C4 は既 closed。**次は in-vivo シェイクダウン（runsheet）。**

### C1（pixel size）closed（2026-06-23）
- **root cause**: SI 2026 は `hSI.objectiveResolution ↔ hSI.hMotors.hCSMicron` が link（changelog 確認）。**MDF scalar 編集は persist 済み classData に shadow される**＝前回 15 復帰の真因。**正しいノブは live property `hSI.objectiveResolution`**（set すると hCSMicron 自動追従・classData に persist・full restart 生存）。**指紋＝`hCSMicron.toParentAffine` 対角 = `1/objRes`**。
- **2対物 graticule 較正**（R1L3S3P1・**long-baseline 2交点法**）:
  | 対物 | objectiveResolution | µm/px | px/µm | FOV | NA |
  |---|---|---|---|---|---|
  | 25xOlympus | 37.2 | 0.981 | 1.019 | 502µm | — |
  | 10xThorlabs TL10X-2P | 44.85 | 1.182 | 0.846 | 605µm | 0.5 |
  - 各2本一致（25×: 0.9799/0.9817・10×: 1.1819/1.1831）・X/Y 等方。dump で reported = graticule 実測一致を確認（PASS 判定は実測一致で見る・`0.908` ハードコードは使わない）。
  - **near-DC FFT は不可**（512px に格子 7-8 周期＝分解能不足で偽値 0.72/0.80 を出した）→ long-baseline 2交点法が正。
- **multi-objective 運用A（実機実証）**: active classData = **default 固定**。named（`<対物>-CoordinateSystems_classData.mat`）は **copyfile で出し入れ**（`hCS.save()`/`hCS.load()` は引数なし＝active=classDataFileName が指す先のみ触る）。
  - **MDF `classDataFileName` は default 固定・named を絶対に指さない**（指すと acquisition/exit で active=named が live 値に汚染される＝今回事故＋復旧を経験）。
  - save: `hCS.save(); copyfile(DEF, named)` / load: `copyfile(named, DEF); hCS.load()`。
  - load 往復 verify 済: 25x→37.2 / 10x→44.85。
- **3重保護**: named classData ＋ MDF seed（`objectiveResolution=37.2`）＋ repo 台帳 `objective_calibration.yaml`（2項）。
- **contract 凍結**: `contracts/c1_pixel_size/c1_25xOlympus_ref.json` ＋ `c1_10xThorlabs_TL10X2P_ref.json` ＋ `objective_calibration.yaml`。
- **CoordinateSystems 実パス**: `C:\Users\KeioPharmMicroscopy2\Documents\MATLAB\MicroscopeMDF.ConfigData\2026\CoordinateSystems\`。
- **figure 影響**: `--px-per-um 1.1` は両対物とも誤り（25× は +8%）→ **metadata 由来へ（A-4・解析側）**。
- env: `mcd-quicklook` に `tifffile` 追加（dump 依存）。
- **A-5（SI metadata SOP）突合済**: logFileStem 規約（modality UPPERCASE/dataset/sub-ses-cond-run/SI 連番）・ALS 3ファイル（`.meta.txt`/`.pmt.dat`/`.scnnr.dat`）presence・scan_mode は metadata 由来（ファイル名非依存）。

### 既 closed（やり直さない）
- **ゲート②（deterministic fixed-frame injection）=PASS（06-18）**: WG は ALS 下で arm 不安定（§3.5）→ injector を D3.2 raw DoTask（finite・trig `/vDAQ0/D2.2`/rising・`syncArmStart` で acqModeStart auto-arm）で駆動。3 run（4-line/8ms/1000cyc/N=500）で head_pad 2.23/1.98/1.16s ばらつき下も **着弾 cycle 全て #501**。150ms 単発 5.08V・diag_ttl clean。`N=目標cycle−1`。
- **ゲート①（1-min scan stop）=closed（06-12）**: 原因＝有限 `framesPerSlice`（ALS=cycle 数）→ `Inf` で持続。
- **R1（契約 emission）=PASS（06-19）**: `make_trigger_sync` 単一正本・3 run sidecar VALID・inject_cycle #501・cycle_period 自動取得（`hRoiManager.scanFramePeriod`）。
- **C2（behavior を契約に）=closed（06-20）**: schema **0.3.0**（`recorded_channels`）・実 ALS VALID・inject #501・1000/1000・`als_datafile` basename・behavior_sidecar deprecate。
- **C3（recorder 末尾切れ）=resolved（06-20）**: stop 2-3s 余白で 1000/1000。
- **C4（behavior EMI）=resolved（06-20）**: `emi_quant` で **50Hz mains 主体**（scanner 副次）＝scanner EMI 疑いを訂正。対策＝接地（B）。
- **GUI v2（06-20）**: target-cycle 直接入力（N=target−1）・STALE+Apply&Arm・cycle period auto-track。

---

## 2. Tier 順（次手）

- **Tier0（実機・sync 正本）**: galvo ✓ / ALS ✓（single + multi-line/3-line/4-line）/ resonant＝据え置き。
- **契約ゲート（(A)）**: ①②R1C2C3C4 + **C1 = 全 closed＝完全クローズ**。
- **次（spine）**: **in-vivo シェイクダウン（`in_vivo_migration_runsheet.md`）**。preflight G1（C1）は本日クリア済。
- **並行（B・動物不要）**: figure metadata 由来化（A-4）/ QC guard（objRes!=15・対物期待値突合）/ behavior mains 接地 / コード配置移送 / ALS CNR phantom。
- **(C) 据え置き（不可逆前ゲート・今ではない）**: awake/vasomotion-intact・plasma tracer ref・vessel-type ID・fast-SRS feasibility。

---

## 3. 同期・injector（確定）

- **injector = DoTask v4（fixed-frame）**: D3.2 raw `DoTask`（finite・trig `D2.2`/rising・`syncArmStart` で acqModeStart auto-arm）。WG 案は廃止（ALS 下で `linePeriod` assert・`[sync] armed` 偽陽性）。`N=目標cycle−1`。
- **frame clock 配線**: D0.0 out（所有ロック）→ 物理 T 分岐 → AI6（記録）＋ D2.2（trigger 入力）。
- **t0 正本** = Data Recorder AI7 TTL エッジ（scan-mode 非依存）。
- **cycle_period** = live `hRoiManager.scanFramePeriod`（`alsCyclePeriodS` 単一正本・ハードコード廃止）。
- 物理到達遅延は `physical_delay_offset_s`（定数・t0 に折り込まない）。
- **GUI v2 完了**: target-cycle 直接入力・STALE+Apply&Arm・cycle period auto-track。

---

## 4. 既知の注意

- **C1 pixel size（06-23 closed）**: 正しいノブは **live property**（MDF scalar は classData に shadow＝前回罠）。対物切替は **copyfile で named↔default → `hCS.load()`**（A 運用）。**classDataFileName は default 固定**（named を指すと active 汚染＝今回事故）。指紋 hCSMicron 対角=1/objRes。graticule は long-baseline 2交点法（near-DC FFT 不可）。
- **1-min scan stop（closed）**: 有限 `framesPerSlice` → `Inf`。raster 切替時は再設定。
- **injector（DoTask v4）**: WG 廃止。`cfgSampClkTiming` は 'not done'→property 代替・`sampleMode` 既定 continuous→finite 必須・D3.2 は WG Remove で解放。
- **recorder 末尾切れ（cosmetic）**: head_pad 大の run で末尾数 cyc を切るだけ。stop 2-3s 余白で 1000/1000。
- **behavior EMI = mains 50Hz 主体**: 対策＝接地（B・rig）。treadmill は Sawtelle teensy decoded speed/dir（無動物=speed≈dir）。
- **ALS ROI GUI Add バグ（4-line）**: 回避＝SI 再起動／保存 ROI ロード／2-line 複製／programmatic builder。
- **Optimize Waveform 不可（MBF 25850）**: Reset Waveform → Calibrate + Test。
- **掃引品質**: `sweep_quality.py` で `.scnnr.dat` per-cycle pp（5th percentile が線サイズ相当で PASS・park 病検出）。
- **SI 起動中 `clear functions`/`clear all` 厳禁**（MDF/resource unload）。flush は `clear <関数名>` のみ。
- **env**: `mcd-quicklook`（`tifffile` 追加済・dump 依存）。

---

## 5. 解析側への申し送り

> loader は依存軽量（numpy+h5py）で取得 repo `src/python` に single source、解析が一方向 import。schema validation は jsonschema（ivwib）。

- **P1/P2 完了**: galvo go 数値確定／`als_loader ↔ readLineScanDataFile` exact（single+multi-line）。
- **③ harness `als_inject_align.py`**: branch A/B・residual・`als_datafile_timing` emit。
- **`diag_ttl.py` / `sweep_quality.py` / `emi_quant.py`**: TTL 特徴づけ／掃引品質／EMI 定量（mains 切り分け）。
- **R1（契約 emission）closed**: `make_trigger_sync.py` 単一正本（`SCHEMA_VERSION=0.3.0`・`recorded_channels`・`als_datafile` basename・`schema_version` const pin）。`als_inject_align --emit-sidecar` は委譲。
- **Layer-2 QC**: `qc_core.py`（UI 非依存・1 dict）＋ `qc_dashboard.py`（PyQtGraph・`.meta.txt` 有無で ALS/galvo 自動判定）。
- **C1（06-23・最重要・下記詳細）**: pixel size を実機 graticule で確定 → **`--px-per-um 1.1` 廃止・metadata 由来（対物別）へ**。1.1 は誤り（25× +8%）で過去成果は再導出。25xOlympus=0.981µm/px・10xThorlabs=1.182µm/px。詳細は解析側 handoff `handoff_20260623.md`（または本節）。
- **time-0 設計**: 撮像アンカー=cycle 1／ダイナミクスアンカー=注入 TTL（cycle 1-500 baseline・501 から post）・定数 501 cyc≈4.0s で変換。

---

## 改訂履歴

| 日付 | 変更 |
|---|---|
| 2026-06-23 | **C1（pixel size・SI metadata SOP）closed＝(A) engineering ゲート完全クローズ**（実機＋graticule）。root cause: SI2026 は objectiveResolution↔hCSMicron link・MDF scalar 編集は persist 済み classData に shadow＝前回 15 復帰の真因→正しいノブは live property（hCSMicron 自動追従・persist・指紋 対角=1/objRes）。2対物 graticule 較正（R1L3S3P1・long-baseline 2交点法・near-DC FFT は分解能不足で不可）: 25xOlympus 37.2/0.981µm/px/502µm、10xThorlabs TL10X-2P(NA0.5) 44.85/1.182µm/px/605µm（各2本一致・X/Y 等方・dump reported=実測一致 PASS）。multi-objective 運用A（active=default 固定・named は copyfile・save/load は引数なし=active のみ・classDataFileName は named 不可=指すと汚染→今回事故/復旧・load 往復 verify）。3重保護（named mat＋MDF seed 37.2＋yaml 台帳）。contract: c1_25xOlympus_ref.json/c1_10xThorlabs_TL10X2P_ref.json/objective_calibration.yaml。CoordinateSystems 実パス=MicroscopeMDF.ConfigData\2026\CoordinateSystems\。figure は --px-per-um 1.1（+8% 誤）廃止→metadata 由来（A-4）。env に tifffile。A-5（logFileStem/ALS3ファイル/scan_mode=metadata）突合済。 |
| 2026-06-20 | **in-vivo 準備: C2 behavior 契約 closed（schema 0.3.0 recorded_channels・実 ALS VALID・inject #501）＋C4 EMI=mains 訂正＋C1 pixel-size 摘発（pending）＋GUI v2（target-cycle 直接・STALE+Apply&Arm）**。in-vivo runsheet 作成。コード配置決定（figure→解析）。 |
| 2026-06-19 | **R1（契約 emission）PASS＋cycle_period 自動化＋emitter 一本化**。3 run sidecar VALID・inject #501。`make_trigger_sync` 単一正本（schema const pin）。 |
| 2026-06-18 | **ゲート② PASS＝injector を DoTask v4 で deterministic fixed-cycle 化（WG 廃止）**。3 run #501 不変。GUI v1。scanimage_vdaq_internals.md 新規。 |
| 2026-06-12 | **ゲート①（1-min stop）closed＝有限 framesPerSlice→Inf＋②機構特定（frame-clock hardware-trigger）**。 |
| 2026-06-09 | ALS multi-line（3-line）go・sweep_quality.py 新規。 |
| 2026-06-08 | ALS single-line go（branch A clock・配線変更ゼロ）。diag_ttl/als_inject_align 新規。 |
| 2026-06-06 | 解析側 P2 single-line exact・trigger_sync emitter galvo VALID。 |
| 2026-06-05 | 方式A e2e galvo go。Data Recorder 配線・HDF5 レイアウト確定。 |