# NEXT SESSION kickoff — 取得側（次回）

```
last_updated:   2026-06-19
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正・2026-06-19 reconciled）
reflects:       status.md（取得側 bench 正本）/ roadmap（0618b＋0619 当て込み済）
scope:          次セッションの頭出し。状態の正本＝status.md / roadmap。
                本 doc は「次に何を・どの順で・なぜ」だけ。
```

> 起動時: 古い kickoff を current 扱いしない。`last_updated` を確認。状態は status.md / roadmap が正。

---

## 0. いまの地点（1 段落）

**本番前ハードウェアゲート①②とも closed・契約 emission（R1）も PASS。** ①（1-min stop）＝有限 `framesPerSlice` → `Inf` 化で解決。②（deterministic fixed-frame injection）＝WG は ALS で arm 不可ゆえ廃止、自前 `DoTask`（v4）で PASS（3 run・head_pad 1.15–2.23s ばらつき下でも `inject_cycle=#501` 不変＝frame-clock anchored）。R1（契約 emission・gate 条件2 の emission 部）＝PASS（sidecar v0.2.0 VALID・`make_trigger_sync` 単一正本）。cycle_period は hSI 自動取得（`scanFramePeriod`/`alsCyclePeriodS`）で done。Layer-2 QC dashboard 第一弾 done。**roadmap は 2026-06-19 に status へ追いつき済（0618b science 橋渡し＋0619 R1 PASS を当て込み・優先序列 flip は保留）。**

---

## 0.5 ゲートの正直な見取り図（A/B/C・scope creep 防止の背骨）

> 「①②完了」は **契約（engineering）ゲート**の話。systemic-water pivot（roadmap §0.5）が新たに持ち込んだ
> **feasibility（science）ゲート**は1つも検証されていない。両者を混ぜると、契約 polish の達成感で
> **awake 未検証のまま不可逆取得に走る**。下記3バケツを分けて維持する（roadmap §4/§5 と整合）。

- **(A) どんな in-vivo grab にも要る最小 engineering ゲート** ＝ **残り1個: SI 自動 metadata の実機 SOP 検証**のみ。≒closed 直前。これが通れば契約ゲートは全開。
- **(B) 動物不要・可逆/オフラインの science de-risk** ＝ いつでも・最安。**(C) を不可逆取得の前に最も安く潰す枠**。特に ALS CNR phantom → SNR feasibility は「systemic-water の方向性 readout がそもそも feasible か」を **awake 手術1件もやる前に**答える。
- **(C) systemic-D2O 不可逆取得の前に閉じる新ゲート**（roadmap §0.5/§4 後段 gate）＝ awake/vasomotion-intact ・ plasma tracer ref ・ vessel-type ID ・ fast-SRS feasibility。**(A) に溶かさない。今セッションのゲートではない。**

---

## 1. 次セッションでやること（優先順）

### (A) spine ＝ 契約ゲートを閉じる（rig・最小・安い）
1. **SI 自動 metadata の実機 SOP 検証（gate 条件2 の残り）**: logFileStem SOP・ALS 3 ファイル（`.meta.txt`/`.pmt.dat`/`.scnnr.dat`）＋`scnnr`・「acq / scan_mode はファイル名でなく metadata」が契約どおりか実機で突合（手順＝runsheet §4.5）。追加 grab 不要（既存 gate② 採用 run でも可）。**通れば (A) 完全 close ＝契約ゲート全開。**

### (A 相乗り) 同じ grab で2件まとめて潰す（別 grab を増やさない）
2. **behavior 記録を契約に載せる**: `AI4=treadmill_dir` / `AI5=treadmill_speed` を Data Recorder（同 vDAQ clock・同 HDF5）→ `datarecorder_loader` 取り込み → `signals.behavior` 整合 → schema に behavior ch を確定。range_v は実測で確認。
3. **behavior ノイズ onset の切り分け**: `treadmill_speed` のノイズ立ち上がりが head_pad（撮像 start）に一致 → **無動物・scanner ON** で scanner EMI pickup か実信号かを判定。in-vivo で behavior を解釈する前の前提。

### (B) 動物不要 de-risk（near-term・science の本丸 risk 低減）
4. **ALS CNR/dwell @ D2O-in-water phantom line**（最高レバレッジ・保留解除候補）: `sweep_quality` の per-cycle σ で CNR/dwell を測る（既存 slice light/dark ALS は detector noise floor のみ＝D2O コントラストは phantom 較正が要る）→ **SNR feasibility model（対流上限）を unblock**。null（方向性ゼロ）も結果＝無摂動で対流上限を与える。
5. **ALS×raster overlay 実データ検証**: `als_loader.scanfields()` 出力を `ScanField` に adapt → 実 1Hz galvo frame の overlay。**ついでに `.scnnr.dat` 988 vs pmt/clock 1000 の tail-clip が先頭/末尾どちらか確定**（per-cycle pmt↔feedback 対応のズレ位置）。物理 µm 正確さは PIXEL_SIZE_UM 実 FOV 較正待ち＝それまで reference/pixel 空間で registration 検証のみ。
6. **解析一本化**: 散在ツール（datarecorder/als loader・compare_als_ref・make_trigger_sync・als_inject_align・diag_ttl・sweep_quality・qc_core/dashboard）を raw→sync→per-line→QC の単一パイプラインへ。契約＝`trigger_sync.schema.json`。

### (C) systemic-D2O 不可逆前ゲート（**今セッションのゲートではない**・明示分離）
- awake/vasomotion-intact imaging（麻酔/開頭が NE/vasomotion を殺す＝最大の技術 risk）／plasma tracer 参照ch（BBB 水 delivery と実質 spread の分離）／vessel-type 同定プロトコル（細動脈 vs 細静脈・overlay が幾何基盤）／fast-SRS feasibility（sub-second µm radial kinetics・短 dwell SNR）。実体は roadmap §0.5/§4。**(A) と混ぜない。** これらは Track-M/W flip 裁定（保留中）とも結びつく＝「first in-vivo grab」が麻酔下か awake-vasomotion-intact かを決める。

### 据え置き / 最適化（急がない）
7. FastZ 導入 / injection・behavior GUI 統合 / clock `[CHECK]`→`[OK]` 化（head warmup 取りこぼし・inject_cycle には無害ゆえ任意）。
8. より速い ALS（transit 最短順 / pause 整定 / serpentine）・resonant（hardware 復帰待ち）・NAS（Phase 1.5 安全コピー）。

---

## 2. 実機前チェック（preflight・v4）

- **WG 'TrigLegato130-2' を Resource Config で Remove**（D3.2 解放）してから DoTask を立てる。
- ALS: Optimize 不可 → **Reset Waveform → Calibrate + Test**。
- 取得長: `framesPerSlice`（ALS=cycle 数）を **`Inf`**（or 必要 cycle 数）。raster 切替時は再設定。
- Data Recorder: Sample Rate **5000 Hz**／Auto Start ON／Use Trigger OFF／Duration Inf／`logFramesPerFile=Inf`（per-scanner）。`AI7→Legato130_TTL`・`AI6→frame_clock`（ALS でも cycle clock）・`AI4→treadmill_dir`・`AI5→treadmill_speed`。
- injector（v4 DoTask）: 配線不変（`D3.2`→T→`AI7`＋Legato／`D0.0`→T→`AI6`＋`D2.2`）。N は `syncControlPanel` のフィールド or `setappdata(0,'sync_v4_params',struct('N',狙い cycle))`。`N=目標cycle−1`（+1 オフセット）。
- UF: `acqModeStart→syncArmStart`（v4＝DoTask 構成→start）／`acqAbort`・`acqDone→syncDisarm`（v4＝stop/abort）／**`frameAcquired` 空**。
- **SI 起動中に `clear functions`/`clear all` 厳禁**（MDF/resource singleton を unload）。flush は `clear <関数名>` のみ。UF は Delete→再追加で fresh handle。
- 取得直後 QC: `diag_ttl`（AI7 edges=1）→ `als_inject_align`（inject_cycle）→ `sweep_quality`（per-cycle pp）。または `qc_dashboard`（.h5 1 つで畳む）。
- ツール実行 env: `mcd-quicklook`（`...\GitHub\microscope_control_dev\src\python`）。

---

## 3. 既に閉じた（やり直さない）

- **ゲート① closed（2026-06-12）**: 有限 `framesPerSlice` が原因・`Inf` 化で持続確認。
- **ゲート② closed（2026-06-18・v4 DoTask）**: 3 run inject_cycle=#501 一致・head_pad 変動下でも不変＝frame-clock anchored。**WG 方式は ALS で arm 不可につき却下・再試行しない。**
- **v4 DoTask 罠（再発防止）**: ① `cfgSampClkTiming`='not done'（→`sampleRate` property）② `sampleMode` 既定 continuous（→`'finite'` 必須）③ Vidrio クラスは `.p`（→`methods -full`/`disp(hT)` で introspect）④ D3.2 は WG 予約ゆえ WG Remove 必須。
- **R1（契約 emission）PASS（2026-06-19）**: `make_trigger_sync` 単一正本（0.2.0）・`als_inject_align --emit-sidecar` 委譲・3 run sidecar VALID＋inject_cycle #501。旧 emit の v0.1.0 形は schema INVALID（10 errors）で捕捉。schema `schema_version` を `const` pin。
- **cycle_period 自動取得 done（2026-06-19）**: `hRoiManager.scanFramePeriod` を単一正本 helper `alsCyclePeriodS` 経由で `syncArmStart`/`syncControlPanel` が読む。ハードコード 8ms 廃止・override drift は arm 時 warn。
- **Layer-2 .h5 QC dashboard 第一弾 done（2026-06-19）**: `qc_core`＋`qc_dashboard`。run-01_00004 で contract 値（#501・head_pad 1.155・sweep PASS）再現。
- **roadmap reconcile done（2026-06-19）**: 0618b（science 橋渡し・§0.5・de-risk gate・§9 pointer）＋0619（R1 PASS）当て込み済。**優先序列 flip は保留。**

---

## 4. 未決 / 繰越

- **(A) 残**: SI 自動 metadata の実機 SOP 検証（gate 条件2 の残り）。
- **(B) 起票**: ALS CNR phantom（→ SNR feasibility）／overlay 実データ＋scnnr 988 tail-clip 位置確定／behavior EMI 切り分け／解析一本化。
- **(C) 据え置きゲート**: awake/vasomotion-intact・plasma tracer ref・vessel-type ID・fast-SRS feasibility（不可逆 systemic-D2O の前提・roadmap §0.5/§4）。
- **doc 裁定（保留・要 Taka）**: Track-M vs Track-W の優先序列 flip。これが「first in-vivo grab」の定義（麻酔下か awake か）を決める。
- 投与を cycle 内の特定 line/位置に当てたい場合の N 小数オフセット（現状 cycle 境界 +0.0ms）。
- clock `[CHECK]`（head warmup 取りこぼし）の `[OK]` 化（任意）。

---

## 関連ドキュメント

- 優先順位の正: `in_vivo_water_imaging_brain/docs/strategy_roadmap.md`（2026-06-19 reconciled）
- 取得側 status: `docs/status.md`
- 同期設計: `docs/sync_architecture.md`（§3.5 v4 DoTask）
- runsheet: `docs/method_a_fixedframe_injection_runsheet.md`（§4.5 R1 突合手順）
- 配線: `docs/vdaq_io_map.yaml`（AI4/AI5・WG→DoTask 反映済）
- 契約 schema: `schemas/trigger_sync.schema.json`（v0.2.0）
- UF/GUI: `src/matlab/{syncArmStart,syncDisarm,syncControlPanel}.m`（v4＋GUI v1）
- ツール: `src/python/{datarecorder_loader,als_loader,compare_als_ref,make_trigger_sync,als_inject_align,diag_ttl,sweep_quality,qc_core,qc_dashboard}.py`
- 科学プログラム実体: `docs/strategy/roadmap_parenchymal_transport_2026-06-18.md`（§0.5 pointer）
