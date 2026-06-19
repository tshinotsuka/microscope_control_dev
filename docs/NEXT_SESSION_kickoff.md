# NEXT SESSION kickoff — 取得側（次回）

```
last_updated:   2026-06-18
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
reflects:       session_20260618_summary_and_carryover.md
scope:          次セッションの頭出し。状態の正本＝status.md / roadmap。
                本 doc は「次に何を・どの順で」だけ。
```

> 起動時: 古い kickoff を current 扱いしない。`last_updated` を確認。状態は status.md / roadmap が正。

---

## 0. いまの地点（1 段落）

**本番前ゲート①②とも closed。** ①（1-min scan stop）＝有限 `framesPerSlice` が原因・`Inf` 化で解決。②（deterministic fixed-frame injection）＝WG 方式は ALS で arm 不可（`startTask→computeWaveform→linePeriod` が StimulusField で assert 落ち・却下）→ **自前 `dabs.vidrio.ddi.rdi.DoTask`（v4）で PASS（2026-06-18）**。v4 が ALS 走行中に arm 成功・3 run（N=500）で `inject_cycle=#501` 完全一致（head_pad 1.16–2.23s 変動下でも不変＝frame-clock anchored）。`syncArmStart`/`syncDisarm` を v4（DoTask 構成→start／abort）に確定、**注入 GUI v1（`syncControlPanel`）も実機動作確認**。配線・cycle rate（125Hz/8.0ms・4-line）・behavior（AI4=treadmill_dir / AI5=treadmill_speed）も白。

**追補（2026-06-19）**: R1（契約 emission・gate 条件2 emission 部）＝PASS（3 run で sidecar v0.2.0 VALID・inject_cycle #501）。emitter は `make_trigger_sync` 単一正本化＋`als_inject_align` 委譲（出力 byte 一致）。schema `schema_version` を `const` pin。cycle_period は hSI 自動取得（`hRoiManager.scanFramePeriod`・`alsCyclePeriodS`）で done。**残 gate 条件2＝SI 自動 metadata の実機 SOP 検証のみ**。

## 1. 次セッションでやること（優先順）

### 最優先＝gate 残務（gate 条件2 の残り）
1. **SI 自動 metadata の実機 SOP 検証（gate 条件2 の残り）**: logFileStem SOP・ALS 3 ファイル＋`scnnr`・「acq / scan_mode はファイル名でなく metadata」が契約どおりか実機で確認。R1（契約 emission）は 2026-06-19 PASS 済（§3）。これが通れば **gate 条件2 完了＝in-vivo 不可逆取得の契約ゲートが全部開く**。

### 並行（実機 / オフライン）
3. **behavior 記録・解析起こし**: AI4=treadmill_dir / AI5=treadmill_speed を Data Recorder（同 vDAQ clock・同 HDF5）→ `datarecorder_loader` 取り込み → `signals.behavior` 整合 → 解析。range_v は実測で確認。
4. **解析側 .h5 QC ビューア（Layer-2 最初）＝第一弾 done（§3）**: `qc_core`＋`qc_dashboard`（PyQtGraph）。残＝clock パネル可読化（125Hz 生波形→edge tick）／behavior 行分け等の polish（任意）。
5. **ALS×raster 一枚図 / ALS 解析**: `als_loader.scanfields()` 幾何で 1Hz 参照に ROI/scan line 重畳（horizon の overlay タスク・`compare_als_ref`）＋ per-ROI トレース。
6. **FastZ 導入 / データ解析の一本化 / injection・behavior GUI 統合**: 据え置き。

### 据え置き / 最適化（急がない）
7. clock `[CHECK]`→`[OK]` 化（head warmup 取りこぼし・inject_cycle には無害ゆえ任意）。
8. より速い ALS（transit 最短順 / pause 整定 / serpentine）・resonant（hardware 復帰待ち）・NAS（Phase 1.5 安全コピー）。

## 2. 実機前チェック（preflight・v4）

- **WG 'TrigLegato130-2' を Resource Config で Remove**（D3.2 解放）してから DoTask を立てる。
- ALS: Optimize 不可 → **Reset Waveform → Calibrate + Test**。
- 取得長: `framesPerSlice`（ALS=cycle 数）を **`Inf`**（or 必要 cycle 数）。raster 切替時は再設定。
- Data Recorder: Sample Rate **5000 Hz**／Auto Start ON／Use Trigger OFF／Duration Inf／`logFramesPerFile=Inf`（per-scanner）。`AI7→Legato130_TTL`・`AI6→frame_clock`（ALS でも cycle clock）・`AI4→treadmill_dir`・`AI5→treadmill_speed`。
- injector（v4 DoTask）: 配線不変（`D3.2`→T→`AI7`＋Legato／`D0.0`→T→`AI6`＋`D2.2`）。N は `syncControlPanel` のフィールド or `setappdata(0,'sync_v4_params',struct('N',狙い cycle))`。
- UF: `acqModeStart→syncArmStart`（v4＝DoTask 構成→start）／`acqAbort`・`acqDone→syncDisarm`（v4＝stop/abort）／**`frameAcquired` 空**。
- **SI 起動中に `clear functions`/`clear all` 厳禁**（MDF/resource singleton を unload）。flush は `clear <関数名>` のみ。UF は Delete→再追加で fresh handle。
- 取得直後 QC: `diag_ttl`（AI7 edges=1）→ `als_inject_align`（inject_cycle）→ `sweep_quality`（per-cycle pp）。
- ツール実行 env: `mcd-quicklook`（`...\GitHub\microscope_control_dev\src\python`）。

## 3. 既に閉じた（やり直さない）

- **ゲート① closed（2026-06-12）**: 有限 `framesPerSlice` が原因・`Inf` 化で持続確認。
- **ゲート② closed（2026-06-18・v4 DoTask）**: 3 run inject_cycle=#501 一致・head_pad 変動下でも不変＝frame-clock anchored。**WG 方式は ALS で arm 不可につき却下・再試行しない**。
- **v4 DoTask 罠（再発防止）**: ① `cfgSampClkTiming`='not done'（→`sampleRate` property）② `sampleMode` 既定 continuous（→`'finite'` 必須）③ Vidrio クラスは `.p`（→`methods -full`/`disp(hT)` で introspect）④ D3.2 は WG 予約ゆえ WG Remove 必須。
- 配線・cycle rate（125Hz/8.0ms）・behavior（AI4/AI5）白。schema v0.2.0 finalize（9/9 PASS）。
- **R1（契約 emission・gate 条件2 emission 部）PASS（2026-06-19）**: `make_trigger_sync` 単一正本（0.2.0）・`als_inject_align --emit-sidecar` 委譲・3 run sidecar VALID＋inject_cycle #501（head_pad ばらつき下で不変）。旧 emit の v0.1.0 形は schema INVALID（10 errors）で捕捉。schema `schema_version` を `const` pin。**やり直さない**。
- **cycle_period 自動取得 done（2026-06-19）**: `hRoiManager.scanFramePeriod` を単一正本 helper `alsCyclePeriodS` 経由で `syncArmStart`/`syncControlPanel` が読む。ハードコード 8ms 廃止・override drift は arm 時 warn。
- **Layer-2 .h5 QC ダッシュボード第一弾 done（2026-06-19）**: `qc_core.py`（UI 非依存データ層）＋`qc_dashboard.py`（PyQtGraph・1 ファイル選択で diag_ttl→als_inject_align→sweep_quality を畳む・ALS/galvo 自動判定・mode-general）。run-01_00004 で contract 値（#501・head_pad 1.155・sweep PASS）再現。**新所見**: ① `.scnnr.dat` が 988 cyc＝pmt/clock(1000) より tail-clip 疑い（overlay で要確認）／② behavior ノイズ onset が head_pad に一致＝scanner pickup 疑い（無動物・scanner ON で切り分け）。

## 4. 未決 / 繰越

- SI 自動 metadata の実機 SOP 検証（gate 条件2 の残り）。
- **scnnr 988 vs pmt/clock 1000**: feedback tail-clip の欠けが先頭/末尾どちらか（ALS×raster overlay で確認）。
- **behavior ノイズ onset≈head_pad**: scanner EMI pickup か実信号か（無動物・scanner ON で切り分け・in-vivo behavior 解釈の前提）。
- 解析側ダッシュボード（.h5 QC → ALS×raster 一枚図 → ALS 解析）。
- 投与を cycle 内の特定 line/位置に当てたい場合の N 小数オフセット（現状 cycle 境界 +0.0ms）。
- clock `[CHECK]`（head warmup 取りこぼし）の `[OK]` 化（任意）。

## 関連ドキュメント

- 優先順位の正: `in_vivo_water_imaging_brain/docs/strategy_roadmap.md`
- セッション要約/申し送り: `session_20260618_summary_and_carryover.md`
- 取得側 status: `docs/status.md`
- 同期設計: `docs/sync_architecture.md`（§3.5 v4 DoTask）
- runsheet: `docs/method_a_fixedframe_injection_runsheet.md`（§2' v4）
- 配線: `docs/vdaq_io_map.yaml`（AI4/AI5・WG→DoTask 反映済）
- 契約 schema: `schemas/trigger_sync.schema.json`（v0.2.0）
- UF/GUI: `src/matlab/{syncArmStart,syncDisarm,syncControlPanel}.m`（v4＋GUI v1）
- ツール: `src/python/{datarecorder_loader,als_loader,compare_als_ref,make_trigger_sync,als_inject_align,diag_ttl,sweep_quality}.py`
