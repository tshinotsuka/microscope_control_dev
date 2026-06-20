# NEXT SESSION kickoff — 取得側（次回）

```
last_updated:   2026-06-20
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
reflects:       status.md（取得側 bench 正本）/ roadmap / handoff_summary_20260620.md
scope:          次セッションの頭出し。状態の正本＝status.md / roadmap。
                本 doc は「次に何を・どの順で・なぜ」だけ。
```

> 起動時: 古い kickoff を current 扱いしない。`last_updated` を確認。状態は status.md / roadmap が正。

---

## 0. いまの地点（1 段落）

**本番前ハードウェアゲート①②・契約 emission（R1）は既に closed。今回 contract をほぼ凍結。** C2（behavior を契約に）closed＝`trigger_sync` schema **0.3.0**（`recorded_channels` で .h5 自己記述）・実 ALS で VALID・inject #501・1000/1000。C4（behavior EMI 切り分け）resolved＝`emi_quant` 定量で **50Hz 電源 mains 主体（EMI step 1.42x）**・scanner は副次（目視印象を訂正）。**残る契約ゲートは C1（SI 自動 metadata 実機 SOP）の1点**、その核＝**pixel size**：`objectiveResolution` が SI default **15 のまま未校正**（FOV 202µm 誤報・真 465µm）。MDF で 34.4 に直す**実機作業 pending**（今回反映されず 15 のまま）。injection GUI は **v2**（target-cycle 直接入力・STALE 検出＋Apply&Arm・cycle period auto-track）。

---

## 0.5 ゲートの正直な見取り図（A/B/C・scope creep 防止）

> 「契約 closed 直前」は **engineering ゲート**の話。systemic-water pivot（roadmap §0.5）の **feasibility（science）ゲート**は未検証。混ぜると契約 polish の達成感で **awake 未検証のまま不可逆取得に走る**。3 バケツを分離維持。

- **(A) 最小 engineering ゲート** ＝ 残り **C1（SI 自動 metadata 実機 SOP）1 点**。核＝`objectiveResolution` 校正で pixel size 確定。通れば契約全開。
- **(B) 動物不要・可逆 de-risk** ＝ ALS CNR phantom→SNR feasibility／behavior の **mains 接地対策**（今回 EMI=mains と判明）／overlay 実データ。
- **(C) systemic-D2O 不可逆前の新ゲート** ＝ awake/vasomotion-intact・plasma tracer ref・vessel-type ID・fast-SRS feasibility。**(A) に溶かさない。今回のゲートではない。** in-vivo シェイクダウン（runsheet）はこの (C) を食い潰さない可逆作業。

---

## 1. 次セッションでやること（優先順）

### (A) spine ＝ 契約ゲート C1 を閉じる（rig・最小）
1. **C1 pixel size 確定**: MDF `objectiveResolution` を校正値（**≈34.4**＝真 FOV 465µm/13.5°、or graticule 実測）に → **SI 完全再起動**（今回 15 のままだったのは MDF が稼働 SI に届かず＝ロード中 MDF パス確認＋full restart、Premium2026 は Objectives マネージャ管理の可能性）→ `python dump_si_metadata.py "<raster>_00001.tif" --json c1_ref_raster.json` ＋判定ワンライナーで **`C1 PASS`（0.908µm/px・FOV465）**確認 → `c1_ref.json` を contract に凍結。
2. **SI metadata 実機 SOP の残り**: logFileStem SOP・ALS 3 ファイル（`.meta.txt`/`.pmt.dat`/`.scnnr.dat`）・「acq/scan_mode は metadata（ファイル名でない）」突合（追加 grab 不要・既存 gate② run で可）。→ 通れば **(A) 完全 close**。

### (A 済) 今回 closed（やり直さない）
- **C2 behavior を契約に**: schema 0.3.0 `recorded_channels`（name/ai/role/units/range_v）＋`n_samples`、`make_trigger_sync` emit（ROLE_MAP・未マップ raise）、実 ALS VALID。`behavior_sidecar`(method-B) deprecate。
- **C4 behavior EMI 切り分け**: `emi_quant` で **mains 50Hz 主体**（scanner 副次 1.42x）。

### (B) 動物不要 de-risk
3. **behavior 健全性（rig）**: treadmill 手回しで speed/dir デコード確認（speed 0→2.5V@100mm/s・逆回しで dir 反転）＋ encoder/アナログ出力線の **50Hz mains 接地対策**（シールド/差動/スター GND）。
4. **コード配置移送**（cross-repo）: figure 群（F1/F2/F3/als_overlay_panel/als_raster_overlay）を解析 `src/ivwib/viz/` へ。手順＝解析 repo に置き commit→取得 repo で `git rm` commit→解析 env `pip install -e ../microscope_control_dev`。`dump_si_metadata`/`emi_quant`/`fig_recorder_panel` は取得側に残す。`*_recorded_channels.*`（マージ済）は削除。
5. **ALS CNR phantom**（保留解除候補・最高レバレッジ）／overlay 実データ検証／解析一本化（roadmap (B)）。

### (C) systemic-D2O 不可逆前ゲート（**今回のゲートではない**）
- awake/vasomotion-intact・plasma tracer ref・vessel-type ID・fast-SRS feasibility（roadmap §0.5/§4）。**in-vivo シェイクダウン（runsheet）でこれらを食い潰さない**。

---

## 2. 実機前チェック（preflight・v4 ＋ 今回追加）

- **C1**: MDF `objectiveResolution` 校正済か（dump で 0.908µm/px・`C1 PASS`）。未済なら figure は `--px-per-um 1.1` 維持。
- **behavior 接地**: 無動物 scanner-OFF/ON で `emi_quant` → mains 床確認（接地対策後に再測）。
- **WG 'TrigLegato130-2' を Resource Config で Remove**（D3.2 解放）→ DoTask。
- ALS: Optimize 不可 → **Reset Waveform → Calibrate + Test**。
- 取得長: `framesPerSlice`（ALS=cycle 数）を **`Inf`**。raster 切替時は再設定。
- Data Recorder: 5000Hz／Auto Start ON／**stop は grab 後 2–3s 余白**（recorder 末尾切れ回避）。`AI7→Legato130_TTL`・`AI6→frame_clock`・`AI4→treadmill_dir`・`AI5→treadmill_speed`。
- injector（v4 DoTask）: 配線不変。**GUI v2 で着弾 cycle # を直接入力**（内部 N=target−1）→ armed 中に変えたら **Apply & Arm**（STALE バナーが出る）。cycle period は auto-track。
- UF: `acqModeStart→syncArmStart`／`acqAbort`・`acqDone→syncDisarm`／`frameAcquired` 空。
- **SI 起動中 `clear functions`/`clear all` 厳禁**。flush は `clear <関数名>` のみ。
- 取得直後 QC: `diag_ttl`→`als_inject_align`→`sweep_quality`（or `qc_dashboard`）。env＝`mcd-quicklook`。

---

## 3. 既に閉じた（やり直さない）

- **ゲート①②・R1 closed**（2026-06-12/18/19）: framesPerSlice=Inf／DoTask v4 fixed-frame（inject #501 不変）／make_trigger_sync 単一正本・cycle_period 自動取得。
- **C2 behavior 契約（2026-06-20）**: schema 0.3.0 `recorded_channels`・実 ALS VALID・`als_datafile` basename 化・behavior_sidecar deprecate。
- **C4 behavior EMI（2026-06-20）**: `emi_quant` で mains 50Hz 主体（scanner 副次）。新所見②（scanner EMI 疑い）を訂正。
- **C3 recorder 末尾切れ（2026-06-20 再確認）**: stop 2–3s 余白で 1000/1000（run-03 CLEAN）。
- **GUI v2（2026-06-20）**: target-cycle 直接入力・STALE+Apply&Arm・Test fire・cycle auto-track（scanFramePeriod）。

---

## 4. 未決 / 繰越

- **C1（残・実機）**: `objectiveResolution` 校正（default 15→≈34.4）＋SI metadata SOP 突合。
- **behavior**: mains 接地対策（rig）／speed-dir デコードのベンチ確認。
- **配置移送**: figure→解析 repo（cross-repo・上記手順）。
- **(C) 据え置きゲート**: awake/vasomotion-intact・plasma tracer ref・vessel-type ID・fast-SRS（roadmap §0.5/§4）。
- **doc 裁定（保留・要 Taka）**: Track-M vs Track-W 優先序列 flip。
- 投与を cycle 内の特定 line/位置に当てる N 小数オフセット（現状 cycle 境界）。

---

## 関連ドキュメント

- 優先順位の正: `in_vivo_water_imaging_brain/docs/strategy_roadmap.md`
- 取得側 status: `docs/status.md` ／ 解析側ログ: `handoff_summary_20260620.md`
- runsheet: `docs/in_vivo_migration_runsheet.md`
- 同期設計: `docs/sync_architecture.md`（§3.5 v4 DoTask）
- 配線: `docs/vdaq_io_map.yaml`
- 契約 schema: `schemas/trigger_sync.schema.json`（**v0.3.0**）
- UF/GUI: `src/matlab/{syncArmStart,syncDisarm,syncControlPanel}.m`（v4＋GUI **v2**）
- ツール: `src/python/{datarecorder_loader,als_loader,make_trigger_sync,als_inject_align,diag_ttl,sweep_quality,qc_core,qc_dashboard,dump_si_metadata,emi_quant}.py`
