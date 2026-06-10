# NEXT SESSION kickoff — 取得側（次回＝実機あり）

```
last_updated:   2026-06-09
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
reflects:       handoff_summary_20260609.md（解析側ログ・本 kickoff はその前向き要約）
scope:          次セッション（実機あり）の頭出し。状態の正本＝status.md / roadmap。
                本 doc は「次に何を・どの順で」だけ。
```

> 起動時: 古い kickoff を current 扱いしない。`last_updated` を確認。状態は status.md / roadmap が正。

---

## 0. いまの地点（1 段落）

方式A **galvo go ＋ ALS go（single-line ＋ multi-line/3-line）**。3-line（run-01_00005）で ①overflow 無 ②injector 単発5V clean・競合無 ③branch A clock 5000/5000 [OK]・residual 2.1974s、さらに `sweep_quality.py` で **掃引品質 PASS**（per-cycle pp 一定＝park 病なし）＝multi-line の per-line 解析の前提が成立。sync 正本は galvo+ALS で実機確定。**resonant 据え置き／4-line はできる見込みで skip**。残りは **本番前ゲート 2 件**＝これが通れば in-vivo 実験移行を検討。

## 1. 次セッションでやること（実機・優先順）

### 最優先（本番前ゲート・通れば実験移行）

1. **1-min scan stop の原因探索＋改善**（in-vivo は数分連続が要る独立ゲート）。
   - **まず有限フレーム数を疑う**: 166.67 Hz×60 s≈10000 cyc＝既出「10000/10000 edges」運用と符合。`hSI.hStackManager.framesPerSlice` / `acqNumFrames` / ALS cycle 数 / `hScan2D.logFramesPerFile` を確認 → **Inf 化して長め grab を再試**。
   - 停まらなければ: ②166 Hz の frame queue / display buffer overflow（display off・低 rate で切り分け）③Data Recorder の sample 上限 ④PMT+scnnr+recorder 同時書込みの D: スループット。
   - **停止時に必ず console / `disp(lasterr)` を確保**（前回 ROI バグで取り損ねた教訓）。改善後、数分連続 grab を 1 本通す。
2. **決まったフレームでの投与（fixed-frame injection）の導入**。
   - 現行 `delaySec=6`（host timer）は head_pad 可変ゆえ毎回違う cycle に当たる（今回 #655）。**deterministic cycle で撃つ**機構へ。
   - 候補を実機切り分け: ①ScanImage **targetFrame trigger** が ALS で使えるか ②**vDAQ FPGA** で既存 frame_clock（D0.0）エッジを数え **cycle N で injector TTL 発火** ③branch A clock を counter 入力に。**per-frame host UF は overflow ゆえ不可**。
   - 検証: 複数 run で `als_inject_align.py` が **毎回同じ cycle 着弾**を示すこと。

### 並行（上記と並走・実機 / オフライン混在）

3. **behavior 記録・解析**: behavior ch を Data Recorder（同 vDAQ clock・同 HDF5）へ拡張 → `datarecorder_loader` 取り込み → 解析起こし。`trigger_sync` の `signals.behavior` と整合。
4. **FastZ 導入**: fast focus を vDAQ clock 同期で ALS / imaging に統合（多深度）。`sync_architecture.md` に FastZ 波形のクロック整合を追記。
5. **データ解析の一本化**: 散在ツールを raw→sync→per-line→QC の単一パイプラインへ。loader は取得 repo single source・ivwib 一方向 import を維持。契約＝`trigger_sync.schema.json`。
6. **injection / behavior GUI**（5 の先）: `syncControlPanel.m` 起点に operator UX 集約。

### 据え置き / 最適化（急がない）

7. **4-line 取得**: できる見込みで skip。GUI Add バグ再現時のみ programmatic builder（用意済）。
8. **より速い ALS（pause→line 以外）**: 次回最適化案。①transit 最短順（端点 greedy chain）②pause を整定最小まで詰める ③**連続 waypoint serpentine**（線間 pause を消し beam-on のまま折り返す＝dead transit 削減・連結区間は解析で破棄）。まず run-01_00005 で pause/line 時間比を測り overhead 定量化。
9. **trigger_sync finalize（galvo+ALS 2 mode）**: als_datafile gap・`$id`・`signals.behavior`・`als_datafile_timing` ブロック。
10. **resonant**: hardware 復帰まで据え置き。/ **NAS**: Phase 1.5 安全コピー（不可逆 in vivo の前に冗長化）。

## 2. 実機前チェック（preflight）

- ALS: Optimize 不可 → **Reset Waveform → Calibrate + Test**。als_ref / sweep 確認の回は **Monitor Scanner Feedback ON**。
- Data Recorder: Sample Rate **5000 Hz**／Auto Start ON／Use Trigger OFF／Duration Inf。`AI7→Legato130_TTL`・`AI6→frame_clock`（ALS でも cycle clock＝branch A）。**`logFramesPerFile=Inf`**（per-scanner）。
- UF: `acqModeStart→syncArmStart` / `acqAbort・acqDone→syncDisarm` / **`frameAcquired` 空**。
- injector: 現状は `delaySec=6`。fixed-frame 導入後はその機構で発火。grab 開始で console に `[sync] armed → ON → OFF`。
- 取得直後: `diag_ttl.py`（AI7 単発5V・1 edge）→ `als_inject_align.py`（clock [OK]・着弾 cycle）→ `sweep_quality.py`（per-cycle pp PASS）。

## 3. オフラインで既に閉じた（次回やり直さない）

- **ALS bench go/no-go ①②③**: single-line（2026-06-08）＋ **multi-line/3-line（2026-06-09・run-01_00005）**。branch A clock・residual 測定・injector cycle 着弾。
- **掃引品質 PASS（multi-line・run-01_00005）**: `sweep_quality.py` per-cycle pp 一定（park 病なし）。
- **P2 multi-line exact**: `compare_als_ref.py`＝Track-W B loader closed。
- **③ harness `als_inject_align.py`・`diag_ttl.py`・`sweep_quality.py`**: 実機＋fixture で検証済。
- 「per-line 分割を als_ref 突合」案は取り下げ（als_ref に per-line 参照無し）。per-line orientation は下流。

## 4. 未決 / 繰越

- **1-min stop の真因**（有限フレーム数 vs buffer）／**fixed-frame 手段の選択**（targetFrame / FPGA counter）。
- **per-line orientation/flip**: クリーン multi-line 取得済 → 線軸射影で下流 kymograph 前処理。
- **trigger_sync finalize**・**resonant**・**NAS**（上記 9/10）。
- **commit 候補（今セッション分）**: `sweep_quality.py`・in-place の `status.md` / 本 kickoff / `handoff_summary_20260609.md`／roadmap 反映（断片）。

## 関連ドキュメント

- 優先順位の正: `in_vivo_water_imaging_brain/docs/strategy_roadmap.md`
- 解析側ログ: `in_vivo_water_imaging_brain/docs/handoff/handoff_summary_20260609.md`
- 取得側 status: `docs/status.md`
- 同期設計: `docs/sync_architecture.md`
- ALS bench 手順: `docs/method_a_als_bench_runsheet_*.md`（親 SOP `sops/method_a_e2e_gonogo_sop.md`）
- 契約 schema: `schemas/trigger_sync.schema.json`
- ツール: `src/python/{datarecorder_loader,als_loader,compare_als_ref,make_trigger_sync,als_inject_align,diag_ttl,sweep_quality}.py`
