# NEXT SESSION kickoff — 取得側（次回）

```
last_updated:   2026-06-23

priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）

reflects:       status.md（取得側 bench 正本）/ roadmap

scope:          次セッションの頭出し。状態の正本＝status.md / roadmap。本 doc は「次に何を・どの順で・なぜ」だけ。
```

> 起動時: 古い kickoff を current 扱いしない。`last_updated` を確認。状態は status.md / roadmap が正。

---

## 0. いまの地点（1 段落）

**(A) engineering ゲート完全クローズ＝契約全開。** 残っていた C1（pixel size・SI metadata 実機 SOP）を 2026-06-23 に両対物で graticule 確定し、前回 pending（objectiveResolution=15 サイレント復帰）を root cause から解明・SOP 化（**live property がノブ・MDF scalar は classData に shadow・persist は classData・指紋 hCSMicron 対角=1/objRes**）。25xOlympus=37.2/0.981µm/px、10xThorlabs TL10X-2P(NA0.5)=44.85/1.182µm/px。multi-objective 運用A（**active=default 固定・named は copyfile 出し入れ・classDataFileName は named を指さない**）を load 往復で実証。①②R1C2C3C4 は既 closed。A-5（SI metadata SOP）突合済。**次は in-vivo シェイクダウン（runsheet）へ。runsheet G1（C1）は本日クリア済み。**

---

## 0.5 ゲートの正直な見取り図（A/B/C・scope creep 防止）

> systemic-water pivot（roadmap §0.5）の feasibility（science）ゲートは未検証。engineering の達成感で awake 未検証のまま不可逆取得に走らない。3 バケツを分離維持。

- **(A) engineering ゲート ＝ 完全クローズ**（C1 + ①②R1C2C3C4 全 closed）。契約全開。
- **(B) 動物不要・可逆 de-risk** ＝ figure を metadata 由来へ（A-4）／QC guard（objRes!=15・対物期待値突合）／behavior の mains 接地対策／ALS CNR phantom／overlay 実データ。
- **(C) systemic-D2O 不可逆前ゲート** ＝ awake/vasomotion-intact・plasma tracer ref・vessel-type ID・fast-SRS feasibility。**(A) に溶かさない。in-vivo シェイクダウン（runsheet）はこの (C) を食い潰さない可逆作業。**

---

## 1. 次セッションでやること（優先順）

### (A 済) 今回 closed（やり直さない）
- **C1 pixel size（2026-06-23）**: 両対物 graticule 較正（25x=37.2/0.981・10x=44.85/1.182・long-baseline 2交点法・X/Y 等方・dump PASS）。multi-objective 運用A 実証（active=default 固定・named copyfile・load 往復 verify）。contract 凍結（json×2＋objective_calibration.yaml）。詳細 status.md §1。
- **A-5 SI metadata SOP**: logFileStem 規約・ALS 3ファイル presence・scan_mode=metadata 由来。突合済。
- 既 closed: ①②R1C2C3C4・GUI v2。

### (spine) in-vivo シェイクダウン（`in_vivo_migration_runsheet.md`）
1. **preflight G1（C1）は PASS 済**（objRes 校正済・figure は metadata 由来で開始・装着対物の objRes を yaml と照合）。
2. 残り preflight: **G2** EMI 床（無動物 scanner-OFF/ON で emi_quant）／**G3** sync・injector arm（`framesPerSlice=Inf`・WG Remove・dry-fire #501）／**G4** fluidics（saline・tubing 充填）／**G5** animal（head-fix・treadmill 空転・eye protection）／**G6** disk・naming（modality UPPERCASE・sub-ses-cond-run・Auto-Start ON・stop 2-3s 余白）。
3. 取得順（runsheet §2）: 1Hz raster ref → 持続 ALS（recorder Auto-Start→scan→injector #501 自動→stop 2-3s 余白）→ N run。
4. per-grab QC（runsheet §3）: `diag_ttl`→`als_inject_align`→`sweep_quality`→`make_trigger_sync v0.3.0` validate（inject_cycle 501・4 recorded_channels）。

### (B) 動物不要 de-risk（並行・主にオフライン/解析側）
5. **figure metadata 由来化（A-4）**: `--px-per-um 1.1` 廃止（25×=1.019/10×=0.846 px/µm・1.1 は両対物とも誤）→ dump の objectiveResolution/um_per_px 由来＝対物切替が自動で正しくなる。対象 F1/F2/F3/als_overlay_panel/als_raster_overlay。
6. **QC guard**: `objectiveResolution != 15` assert ＋ `objective_calibration.yaml` 期待値突合（±tolerance）＋ objective 識別子を metadata/contract に記録。
7. **behavior**: mains 接地対策（シールド/差動/スター GND・対策後 emi_quant 再測）＋ treadmill speed/dir デコードのベンチ確認（手回し・100mm/s=2.5V・逆回しで dir 反転）。
8. **コード配置移送**（cross-repo）: figure 群を解析 `src/ivwib/viz/` へ（解析 repo に置き commit→取得 repo で `git rm` commit→解析 env `pip install -e`）。`dump_si_metadata`/`emi_quant`/`fig_recorder_panel` は取得側に残す。
9. **ALS CNR phantom**（保留解除候補・最高レバレッジ）／overlay 実データ検証。

### (C) systemic-D2O 不可逆前ゲート（**今回のゲートではない**）
- awake/vasomotion-intact・plasma tracer ref・vessel-type ID・fast-SRS feasibility（roadmap §0.5/§4）。in-vivo シェイクダウンで食い潰さない。

---

## 2. 実機前チェック（preflight）

- **C1（対物切替）**: copyfile で `named→default` → `hCS.load()`。装着対物の `hSI.objectiveResolution` を `objective_calibration.yaml` 期待値と照合（指紋 hCSMicron 対角=1/objRes：25x=0.0269/10x=0.0223）。**MDF `classDataFileName` は default 固定・絶対に named を指さない**（指すと active 汚染＝06-23 事故）。`hCS.save()`/`hCS.load()` は引数なし＝active のみ。
- **behavior 接地**: 無動物 scanner-OFF/ON で `emi_quant` → mains 床確認（接地対策後に再測）。
- **WG 'TrigLegato130-2' を Resource Config で Remove**（D3.2 解放）→ DoTask。
- **ALS**: Optimize 不可 → Reset Waveform → Calibrate + Test。
- **取得長**: `framesPerSlice`（ALS=cycle 数）を `Inf`。raster 切替時は再設定。
- **Data Recorder**: 5000Hz・Auto Start ON・**stop は grab 後 2-3s 余白**。AI7→Legato130_TTL・AI6→frame_clock・AI4→treadmill_dir・AI5→treadmill_speed。
- **injector（DoTask v4）**: 配線不変。GUI v2 で着弾 cycle# 直接入力（内部 N=target−1）→ armed 中変更は Apply&Arm（STALE バナー）。cycle period auto-track。
- **UF**: `acqModeStart→syncArmStart` / `acqAbort`・`acqDone→syncDisarm` / `frameAcquired` 空。
- **SI 起動中 `clear functions`/`clear all` 厳禁**。flush は `clear <関数名>` のみ。
- **取得直後 QC**: `diag_ttl`→`als_inject_align`→`sweep_quality`（or `qc_dashboard`）。env=`mcd-quicklook`（tifffile 追加済）。

---

## 3. 既に閉じた（やり直さない）

- **ゲート①②・R1**（06-12/18/19）: framesPerSlice=Inf／DoTask v4 fixed-frame（inject #501 不変）／make_trigger_sync 単一正本・cycle_period 自動。
- **C2 behavior 契約**（06-20）: schema 0.3.0 `recorded_channels`・実 ALS VALID・`als_datafile` basename・behavior_sidecar deprecate。
- **C3 recorder 末尾切れ**（06-20）: stop 2-3s 余白で 1000/1000。
- **C4 behavior EMI**（06-20）: mains 50Hz 主体（scanner 副次）。
- **GUI v2**（06-20）: target-cycle 直接入力・STALE+Apply&Arm・cycle auto-track。
- **C1 pixel size＝(A) 完全クローズ**（06-23）: 両対物 graticule・multi-objective 運用A 実証・A-5 突合済。

---

## 4. 未決 / 繰越

- **behavior**: mains 接地対策（rig）／speed-dir デコードのベンチ確認。
- **A-4 / QC guard / 配置移送 / ALS CNR phantom**（B・主に解析側 or オフライン）。
- **(C) 据え置きゲート**: awake/vasomotion-intact・plasma tracer ref・vessel-type ID・fast-SRS。
- **doc 裁定（保留・要 Taka）**: Track-M vs Track-W 優先序列 flip。
- 投与を cycle 内の特定 line/位置に当てる N 小数オフセット（現状 cycle 境界）。

---

## 関連ドキュメント

- 優先順位の正: `in_vivo_water_imaging_brain/docs/strategy_roadmap.md`
- 取得側 status: `docs/status.md`
- runsheet: `docs/in_vivo_migration_runsheet.md`
- 同期設計: `docs/sync_architecture.md`（§3.5 v4 DoTask）／配線: `docs/vdaq_io_map.yaml`
- 内部仕様: `docs/scanimage_vdaq_internals.md`（C1/objectiveResolution/multi-objective 運用A 追記）
- 契約 schema: `schemas/trigger_sync.schema.json`（v0.3.0）
- C1 contract: `contracts/c1_pixel_size/{c1_25xOlympus_ref.json, c1_10xThorlabs_TL10X2P_ref.json, objective_calibration.yaml}`
- UF/GUI: `src/matlab/{syncArmStart,syncDisarm,syncControlPanel}.m`（v4＋GUI v2）
- ツール: `src/python/{datarecorder_loader,als_loader,make_trigger_sync,als_inject_align,diag_ttl,sweep_quality,qc_core,qc_dashboard,dump_si_metadata,emi_quant}.py`