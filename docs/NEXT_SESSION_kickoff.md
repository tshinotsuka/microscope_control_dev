# NEXT SESSION kickoff — 取得側（次回＝実機あり）

```
last_updated:   2026-06-17
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
reflects:       handoff_summary_20260617.md（解析側ログ・本 kickoff はその前向き要約）
scope:          次セッション（実機あり）の頭出し。状態の正本＝status.md / roadmap。
                本 doc は「次に何を・どの順で」だけ。
```

> 起動時: 古い kickoff を current 扱いしない。`last_updated` を確認。状態は status.md / roadmap が正。

---

## 0. いまの地点（1 段落）

方式A **galvo go ＋ ALS go（single + multi-line・4-line config 取得実績）**。**本番前ゲート①（1-min scan stop）＝closed**（有限 `framesPerSlice` が原因＝fault でなく programmed 完走・`Inf` 化で持続確認）。**②（deterministic fixed-frame injection）＝WG 方式は ALS で行き止まり確定（2026-06-17）**。狙いは host timer を排して injector を frame clock で hardware-trigger することだが、**ScanImage の generic WaveformGenerator は ALS scan mode では arm（startTask）できない**ことが最深部まで実機確定した：`startTask` 自体が毎回 `updateWaveform→computeWaveform→refreshWvfmParams→scannerset.linePeriod` で波形を再計算し、`linePeriod` が raster(ImagingField) 前提で hardcode のため ALS(StimulusField) で必ず assert 落ちする。pre-compute も Show Widget OFF も効かない（startTask 内部の再計算が原因）。`[sync] armed` は偽陽性だった（SI の ErrorHandler が内部エラーを握り潰し、try/catch に伝播せず task 未起動＝AI7 flat）。**配線・cycle rate（125 Hz/8.0 ms・4-line）・WG が撃てること自体・behavior 録りは全部白**。詰まりは「WG task を ALS 中に起こす方法が原理的に無い」点に集約 → **次の一手＝WG をバイパスし自前の `dabs.vidrio.ddi.rdi.DoTask` を D3.2 に立てて D2.2 trigger で撃つ（v4）**。今日 DoTask の API を取得済み。resonant 据え置き。

## 1. 次セッションでやること（実機・優先順）

### 最優先＝本番前ゲート② を閉じる（v4：自前 DoTask）

> ①（1-min stop）は closed・WG 方式は却下。やり直さない（§3）。
> **方針: WG（'TrigLegato130-2'）を Remove して D3.2 を解放 → linePeriod に一切触れない raw DoTask を自分で構成 → start。これが ALS 中に start できるか＝v4 の分水嶺。**

**v4 実装（`syncArmStart` を「DoTask 構成→start」へ）**

1. **D3.2 を解放**: WG 'TrigLegato130-2' を **Remove**（現状 `<Reserved: TrigLegato130-2>` で D3.2 を予約中）。`hDAQ`(=vDAQR1) は `dabs.resources.ResourceStore().filterByClass(...)` 経由 or vDAQ resource から取得。
2. **DoTask を立てる**（acqModeStart UF・骨子）:
   ```matlab
   hT = dabs.vidrio.ddi.rdi.DoTask.createDoTask(hDAQ, 'injTrig');   % static
   hT.addChannel('D3.2');                                           % or hDOs から D3.2
   hT.cfgSampClkTiming(R_Hz, 'finite', nSamp);                      % finite・sample 数
   hT.cfgDigEdgeStartTrig('/vDAQ0/D2.2', 'rising');                 % = frame clock T 分岐
   hT.writeOutputBuffer(pulseVec);   % [zeros(N*cyc*R) ; ones(pw*R)] → 立上り=cycle N
   hT.start();                       % arm: D2.2 立上りで再生開始
   ```
3. **着弾 cycle N** は buffer 前方の zero 長 = `N × cycle_period(8.0 ms) × R` で表現。`R_Hz` は**控えめに**（例 1e5〜1e6）して buffer サイズを現実的に（WG の 2e6 をそのまま使うと `Start=4 s` で 8M sample）。短 HIGH（pw ≈ 0.1–0.2 s）。
4. **DoTask が ALS 中に start するかを実機確認**（= 真の分水嶺・linePeriod を踏まないので通る見込み）。通れば `[sync]` 出力＋（実 grab で）AI7 に単発。
5. **検証チェーン**: ALS ON grab → `diag_ttl.py`（AI7 単発・**edges@2.5V=1**）→ `als_inject_align.py`（着弾 cycle ≈ N）→ **3 run 以上で着弾 cycle 一致** → **ゲート② PASS**。
6. **disarm（syncDisarm v4）**: `hT.stop()` / `abort()` ＋（必要なら）`tristateOutputs` or default low。task ハンドルは persistent/appdata で保持。ライフサイクル（acqModeStart 構成→acqDone 破棄 or 再利用）を決める。
7. **doc 反映**: runsheet（`method_a_fixedframe_injection_runsheet.md`）arm 節と `sync_architecture.md §3.5` を **WG→DoTask に書き換え**。

### 並行（実機 / オフライン混在）

8. **vdaq_io_map.yaml 修正（オフライン・小）**: behavior ch を実測どおり **`AI4=treadmill_dir` / `AI5=treadmill_speed`** に（旧記載 velocity/lick は誤り）。今日 HDF5 signals で確認済。
9. **behavior 記録・解析**: behavior ch（AI4/AI5 確認済）を Data Recorder（同 vDAQ clock・同 HDF5）に乗せ → `datarecorder_loader` 取り込み → 解析起こし。`trigger_sync` の `signals.behavior` と整合。R2 rider は Gate② run に相乗り可。
10. **R1 rider（契約 emission 検証）**: Gate② の grab で `make_trigger_sync` の出力が schema v0.2.0 に VALID か（追加 grab 不要・roadmap gate 条件2）。
11. **FastZ 導入 / データ解析の一本化 / injection・behavior GUI**: 据え置き（変わらず）。

### 据え置き / 最適化（急がない）

12. **4-line 取得**: 機構は line 数非依存・4-line config 取得実績あり（`run-02_00001`）。GUI Add バグ再現時のみ programmatic builder。
13. **より速い ALS**（transit 最短順 / pause 整定詰め / serpentine）・**resonant**（hardware 復帰待ち）・**NAS**（Phase 1.5 安全コピー）。

## 2. 実機前チェック（preflight）

- ALS: Optimize 不可 → **Reset Waveform → Calibrate + Test**。
- **取得長**: 連続取得は `framesPerSlice`（ALS=cycle 数）を **`Inf`**。raster 切替時は再設定。
- Data Recorder: Sample Rate **5000 Hz**／Auto Start ON／Use Trigger OFF／Duration Inf／**`logFramesPerFile=Inf`**（per-scanner）。`AI7→Legato130_TTL`（t0 正本）・`AI6→frame_clock`（ALS でも cycle clock＝branch A）・**`AI4→treadmill_dir`／`AI5→treadmill_speed`**。
- **injector（v4・DoTask）**: 配線は不変 — `D3.2`→T→`AI7`＋Legato／`D0.0`(frame clock)→T→`AI6`＋**`D2.2`**（DoTask の Start Trigger 入力）。**WG は Remove して D3.2 を解放**してから DoTask を立てる。
- UF: `acqModeStart→syncArmStart`（v4＝DoTask 構成→start）／`acqAbort・acqDone→syncDisarm`（v4＝stop/abort）／**`frameAcquired` 空**。
- **SI 起動中に `clear functions`/`clear all` は厳禁**（MDF/resource singleton を unload・復旧＝SI 再起動）。flush は `clear <関数名>` だけ。UF は **Delete→再追加で fresh handle**。
- 取得直後: `diag_ttl.py`（AI7 単発・1 edge）→ `als_inject_align.py`（clock [OK]・着弾 cycle）→ `sweep_quality.py`（per-cycle pp PASS）。
- ツール実行 env: `mcd-quicklook`（`...\GitHub\microscope_control_dev\src\python`）。`python` 直叩き（env アクティブ時）or `$py` フルパス。

## 3. オフライン / 実機で既に閉じた（次回やり直さない）

- **本番前ゲート①（1-min scan stop）closed（2026-06-12）**: 原因＝有限 `framesPerSlice`。`Inf` 化で持続確認（4-line `run-02_00001`・QC 全 PASS）。
- **WG 方式は ALS で行き止まり確定（2026-06-17）＝却下**: `startTask` 自体が `updateWaveform→computeWaveform→linePeriod` で再計算 → ALS(StimulusField) で必ず assert 落ち。pre-compute / widget OFF とも無効。**WG での arm は二度と試さない**。→ DoTask ピボット（§1）。
- **配線・cycle rate・WG 出力経路・behavior は白（2026-06-17 実機）**:
  - frame clock `D0.0→AI6` = **125.0 Hz（8.0 ms/cycle・4-line）** clean train（max ~5V）。**cycle rate 確定**。
  - **D2.2 分岐が生きてる**: D2.2 行きケーブルを空き AI9 で録ると 125 Hz/5V（配線・T 分岐健全）。
  - **WG 本体＋D3.2→AI7 経路**: トリガ無し Test B で clean 単発（edges@2.5V=1・max 5.09V）＝出力経路は正常（＝v4 の DoTask 出力先も同じ D3.2 で実証済）。
  - **behavior**: `AI4=treadmill_dir`／`AI5=treadmill_speed` が HDF5 signals に入る（AI8 reward は skip）。
- **ALS bench go/no-go ①②③**: single-line（06-08）＋ multi-line/3-line（06-09 run-01_00005）＋ 4-line config（06-12 run-02_00001）。掃引品質 PASS（`sweep_quality.py`）。
- **P2 multi-line exact**: `compare_als_ref.py`＝Track-W B loader closed。
- **`trigger_sync.schema.json` v0.2.0 finalize（オフライン）**: galvo+ALS 2-mode・`als_datafile_timing` $def・jsonschema 9/9 PASS（`$id` の host 揃え 1 行 swap が TODO）。

## 4. 未決 / 繰越

- **v4 の分水嶺**: 自前 DoTask が **ALS 中に start できるか**（linePeriod を踏まないので通る見込みだが未確認）。
- **着弾 cycle 指定の実装**: buffer 前方 zero パディング（`N×cyc×R`）方式と `R` のトレードオフ（サイズ）。
- **D3.2 解放手順**（WG Remove）と DoTask のライフサイクル（毎回構成→破棄 or 再利用）。
- **runsheet / sync_architecture §3.5 の WG→DoTask 書き換え**。
- **vdaq_io_map.yaml**: `AI4=treadmill_dir`／`AI5=treadmill_speed` に修正（旧 velocity/lick は誤り）。
- **commit 候補（今セッション分）**: in-place の `status.md`（§1/§2.1②/§3.5/§4/改訂履歴を 2026-06-17 で更新）／本 kickoff／新 `handoff_summary_20260617.md`／schema v0.2.0／（書き換え後）runsheet・sync_architecture §3.5。`syncArmStart.m`/`syncDisarm.m` は **v4（DoTask）確定後**にコミット（v3＝WG は行き止まりにつき置換）。

## 関連ドキュメント

- 優先順位の正: `in_vivo_water_imaging_brain/docs/strategy_roadmap.md`
- 解析側ログ: `handoff_summary_20260617.md`（supersedes 20260612）
- 取得側 status: `docs/status.md`
- 同期設計: `docs/sync_architecture.md`（§3.5 を WG→DoTask に改訂）
- runsheet: `docs/method_a_fixedframe_injection_runsheet.md`（arm 節を v4 に改訂）
- 配線: `docs/vdaq_io_map.yaml`（D0.0→D2.2 済・AI4/AI5 名修正 要）
- 契約 schema: `schemas/trigger_sync.schema.json`（v0.2.0）
- UF: `src/matlab/{syncArmStart,syncDisarm}.m`（v3＝WG・行き止まり／v4=DoTask へ）
- ツール: `src/python/{datarecorder_loader,als_loader,compare_als_ref,make_trigger_sync,als_inject_align,diag_ttl,sweep_quality}.py`
