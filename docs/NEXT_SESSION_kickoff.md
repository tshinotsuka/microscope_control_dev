# NEXT SESSION kickoff — 取得側（次回＝実機あり）

```
last_updated:   2026-06-18
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
reflects:       handoff_summary_20260618.md（解析側ログ・本 kickoff はその前向き要約）
scope:          次セッション（実機あり）の頭出し。状態の正本＝status.md / roadmap。
                本 doc は「次に何を・どの順で」だけ。
```

> 起動時: 古い kickoff を current 扱いしない。`last_updated` を確認。状態は status.md / roadmap が正。

---

## 0. いまの地点（1 段落）

方式A **galvo go ＋ ALS go（single + multi-line/3-line・4-line）**。**本番前ハードウェアゲートは①②とも完了**:
①（sustained 取得／1-min scan stop）＝closed（有限 `framesPerSlice` が原因・`Inf` で数分連続）。
②（deterministic fixed-frame injection）＝**PASS**: WG は ALS 下で arm 不安定（`linePeriod` assert）のため廃止し、**injector を D3.2 の raw DoTask（finite・trig `/vDAQ0/D2.2`/rising・`syncArmStart` で acqModeStart auto-arm）で駆動**。3 run（`run-01_00002`/`00003`/`00004`）で head_pad 1.15–2.23 s ばらつきにもかかわらず **着弾 cycle 全て #501**＝決定論成立。150 ms 単発 5.08 V。
→ 次は **残りの Tier-0**（契約凍結・SI metadata 実機検証・behavior/injector を契約に載せる）＋**injection GUI**（in-vivo 打ち間違い防止）。resonant 据え置き。

## 1. 次セッションでやること（優先順）

> 本番前ハードウェアゲート①②は完了。やり直さない（§3）。in-vivo 移行の残り gate は「契約まわりの Tier-0」＝下記。

### 最優先＝残り Tier-0（in-vivo 不可逆取得の前に必ず閉じる）
1. **behavior / injector を契約に載せる（方式A）**: behavior **も** injector TTL（=t0）**も Data Recorder HDF5**（SI と同 stem・`raw/`。本番前に File Directory を temp から `raw/` へ・`logFramesPerFile=Inf`＝per-scanner）。`trigger_sync.schema.json` を **galvo+ALS の 2 mode で finalize**（`signals.behavior` ch 確定＋`als_datafile_timing` ブロック＋als_datafile gap）。
2. **SI 自動 metadata の実機検証**（logFileStem SOP・ALS 3 ファイル＋`scnnr`・「acq/scan_mode はファイル名でなく metadata」）＝契約 gate。
3. **behavior ch を実配線で確定**（AI4/AI5 等・proposed→confirmed）。Data Recorder で取得 → `datarecorder_loader` 取り込み確認。

### injection GUI（in-vivo 前倒し推奨・打ち間違い防止）
4. **薄い injection 制御 GUI**（`syncControlPanel.m` 起点）。
   - 入力: `N`（or 目標 cycle）・pulse 幅(ms)・enable。ボタン: **Arm**（config 書込み＋DoTask arm）／**Disarm**／（任意）手動 Fire。表示: 現 cycle rate（hSI から）・計算 delay（N×cycle）・armed/idle・直近着弾 cycle。
   - **設計方針**: GUI は config 前面のみ。arm/fire ロジックは `syncArmStart`/DoTask 側に残す（GUI が落ちても acquisition は無事＝loose coupling）。
   - **`N=目標cycle−1`（+1 オフセット）を GUI 内で吸収**＋範囲 sanity check（N<総cycle 等）で in-vivo の致命的打ち間違いを防ぐ。
   - まず injection 単機能で薄く。behavior 統合 GUI は後段。

### 並行（実機 / オフライン混在）
5. **behavior 記録・解析**（Data Recorder 拡張 → `datarecorder_loader` → 解析・`signals.behavior` 整合）。
6. **FastZ 導入**（vDAQ clock 同期・`sync_architecture.md` 追記）。
7. **データ解析の一本化**（raw→sync→per-line→QC・契約＝`trigger_sync.schema.json`・loader single source 維持）。

### 据え置き / 最適化（急がない）
8. **injection cosmetic**: `als_inject_align` の clock 一致を毎回 [OK] にしたいなら **cycle パディング（+10〜20 cyc）** or recorder 余白。現状の 994–996/1000 は recorder 末尾切れ（benign・コマ落ちでない）。
9. **より速い ALS**（transit 最短順／pause 最小化／連続 waypoint serpentine）。
10. **resonant**: hardware 復帰まで据え置き。/ **NAS**: Phase 1.5 安全コピー（取得 PC アクセス設定済・新 raw を `projects/2026_microscope_control_dev/` へ）。

## 2. 実機前チェック（preflight）

- ALS: Optimize 不可 → **Reset Waveform → Calibrate + Test**。als_ref / sweep 確認の回は **Monitor Scanner Feedback ON**。
- **取得長**: 連続取得は `framesPerSlice`（ALS=cycle 数）を **`Inf`**（or 必要 cycle 数）。`framesPerSlice × numSlices × numVolumes` が総 grab frame。raster 切替時は再設定。
- Data Recorder: Sample Rate **5000 Hz**／Auto Start ON／Use Trigger OFF／Duration Inf。`AI7→Legato130_TTL`・`AI6→frame_clock`（ALS でも cycle clock＝branch A）。**`logFramesPerFile=Inf`**（per-scanner）。
- **injector（DoTask v4・PASS）**: 配線 `D3.2`(DoTask)→T→`AI7`＋Legato＋`D2.1`／`D0.0`(frame clock)→T→`AI6`＋**`D2.2`(DoTask Start Trigger)**。`syncArmStart` が acqModeStart で **auto-arm**（widget 手動 Start 不要）。grab 開始で console に `[sync] armed DoTask on D3.2 (finite), trig /vDAQ0/D2.2/rising, target cycle N=...`、終了で `[sync] disarmed`。`N=目標cycle−1`。
- UF: `acqModeStart→syncArmStart` / `acqAbort・acqDone→syncDisarm` / **`frameAcquired` 空**。
- 取得直後: `diag_ttl.py`（AI7 単発・1 edge・150ms）→ `als_inject_align.py`（着弾 cycle・clock）→ `sweep_quality.py`（per-cycle pp PASS）。
- ツール実行 env: `mcd-quicklook`（取得 PC・`...\GitHub\microscope_control_dev\src\python`）。

## 3. 既に閉じた（次回やり直さない）

- **本番前ゲート①（1-min scan stop）closed（2026-06-12）**: 有限 `framesPerSlice` が原因＝fault でない。`Inf` 化で数分連続（4-line `run-02_00001`・QC 全 PASS）。
- **本番前ゲート②（deterministic fixed-frame injection）PASS（2026-06-18）**: **DoTask v4**（D3.2・finite・trig D2.2・`syncArmStart` auto-arm）。`run-01_00002`/`00003`/`00004` で head_pad ばらつき下でも **着弾 cycle 全て #501**＝決定論成立。150ms 単発 5.08V。WG 案は ALS 下 arm 不安定（`linePeriod` assert）で廃止。
- **ALS bench ①②③**: single（06-08）＋3-line（06-09）＋4-line config（06-12）。掃引品質 PASS（`sweep_quality.py`）。
- **P2 multi-line exact**（`compare_als_ref.py`＝Track-W B loader closed）。

## 4. 未決 / 繰越

- **trigger_sync finalize（galvo+ALS 2 mode）**: als_datafile gap・`$id`・`signals.behavior`・`als_datafile_timing`。
- **behavior ch の実配線確定**（proposed→confirmed）。
- **injection GUI**（薄い config 前面＋sanity check・上記 4）。
- **per-line orientation/flip**: クリーン multi-line 取得済 → 線軸射影で下流 kymograph 前処理。
- **N の +1 オフセット**: counting 規約として GUI/SOP に明記（`N=目標cycle−1`）。
- **injection cosmetic**（cycle パディング／recorder 余白）・**resonant**・**NAS**（上記 8/10）。
- **commit 候補（今セッション分）**: in-place の `status.md` / 本 kickoff / 新 `handoff_summary_20260618.md`／`vdaq_io_map.yaml`（D3.2 DoTask 化）／roadmap 反映（gate② PASS）／`syncArmStart.m`（DoTask v4 実体）。

## 関連ドキュメント

- 優先順位の正: `in_vivo_water_imaging_brain/docs/strategy_roadmap.md`
- 解析側ログ: `in_vivo_water_imaging_brain/docs/handoff/handoff_summary_20260618.md`
- 取得側 status: `docs/status.md`
- 同期設計: `docs/sync_architecture.md`（要追記＝DoTask v4・D2.2 trigger・arm 規約。handoff §5 に追記文案）
- 配線: `docs/vdaq_io_map.yaml`（D3.2 DoTask・D0.0→D2.2 反映済）
- ALS bench 手順: `docs/method_a_als_bench_runsheet_*.md`（親 SOP `sops/method_a_e2e_gonogo_sop.md`）
- 契約 schema: `schemas/trigger_sync.schema.json`
- UF/GUI: `src/matlab/{syncArmStart,syncDisarm,syncControlPanel}.m`
- ツール: `src/python/{datarecorder_loader,als_loader,compare_als_ref,make_trigger_sync,als_inject_align,diag_ttl,sweep_quality}.py`
