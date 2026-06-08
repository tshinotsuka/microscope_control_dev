# NEXT SESSION kickoff — 取得側（次回＝実機あり）

```
last_updated:   2026-06-08
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
reflects:       handoff_summary_20260608.md（解析側ログ・本 kickoff はその前向き要約）
scope:          次セッション（実機あり）の頭出し。済んだ分は「済」、実機ゲート分を順序づけ。
                状態の正本＝status.md / roadmap。本 doc は「次に何を・どの順で」だけ。
```

> 起動時: 古い kickoff を current 扱いしない。`last_updated` を確認。状態は status.md / roadmap が正。

---

## 0. いまの地点（1 段落）

方式A **galvo go ＋ ALS go（single-line）**。ALS は **branch A clock が配線変更ゼロで成立**（既存 D0.0→AI6 が ALS cycle clock を載せる）、**residual（head_pad）は毎 grab clock で測定（3.1–3.5 s・可変）**、injector は AI7 path 修正後 **`delaySec=6`（>head_pad）で cycle 着弾**。オフラインで **Track-W B の loader read を multi-line まで closed**（run-01_00002 exact）。新ツール `als_inject_align.py`（③ harness）・`diag_ttl.py`。**resonant は hardware 不在で据え置き**。残りは 4-line 取得・finalize・in vivo gate 準備。

## 1. 次セッションでやること（実機・優先順）

1. **4-line ALS の取得（in vivo は multi-line＝4 本想定）**。前回 **ROI GUI バグで未完**: `ArbitraryLineScanRoiGui>addRoi() (行 77)` → `most.gui.style(uibutton(... 'Add ROI' ...))` でエラー（sync 無関係・console は injector 正常）。手順:
   - 落ちたら**即 `disp(lasterr)` で root エラーを確保**（前回は MATLAB を閉じて取り損ねた）。
   - SI 再起動／保存 ROI group ロード／既存 2-line を複製して足す（Add ボタンを避ける経路）。再現するなら **MBF 報告（Optimize Waveform MBF 25850 と束ねる）**。
   - 波形は **Reset Waveform → Calibrate + Test**（Optimize はベンダーバグで不可）。
   - 取得できたら `als_inject_align.py` で cycle 着弾＋clock `[OK]` を確認、als_ref を export。
2. **掃引品質チェック**: 最近 grab（Reset/Calibrate 運用後）が**毎 cycle 線を掃いているか**を `.scnnr.dat` の cycle 別 pp で確認（旧 run-01_00002 は startup だけで以降 park だった＝波形問題）。pp が線サイズ相当ならOK。
3. **本番前**: Data Recorder File Directory を `temp_data_recorder` → `raw/`・imaging と同 stem。**`hScan2D.logFramesPerFile = Inf`**（per-scanner＝raster でも要設定）。
4. （任意・繰越）**targetFrame / FPGA frame-trigger が ALS で使えるか**確認（「毎回同 cycle で撃つ」を protocol にしたい場合のみ。現状 delaySec で十分）。

## 2. 実機前チェック（preflight）

- ALS: Optimize Waveform 不可 → **Reset Waveform → Calibrate + Test**。als_ref を取る回は **Monitor Scanner Feedback ON**。
- Data Recorder: Sample Rate **5000 Hz**／Auto Start ON／Use Trigger OFF／Duration Inf。`AI7→Legato130_TTL`・`AI6→frame_clock`（ALS でも cycle clock が載る＝branch A）。**`logFramesPerFile=Inf`**。
- UF: `acqModeStart→syncArmStart` / `acqAbort・acqDone→syncDisarm` / **`frameAcquired` 空**。
- injector: **`delaySec > head_pad`（=6 採用）**。`targetFrame` は使わない。grab 開始で console に `[sync] armed → ON → OFF` を確認。
- 取得直後に `diag_ttl.py` で AI7 が単発 5V・1 edge かを即確認（path 不通の早期検出）。

## 3. オフラインで既に閉じた（次回やり直さない）

- **ALS bench go/no-go ①②③（single-line・2026-06-08）**: branch A clock `[OK]`・residual 測定・injector cycle 着弾。
- **P2 multi-line exact**: `compare_als_ref.py` で run-01_00002（2-line・bidi ON）が `max|Δ|=0`＝**Track-W B loader closed（multi-line 含む）**。
- **③ harness `als_inject_align.py`**・**`diag_ttl.py`**: 実 galvo/ALS＋合成 fixture で検証済。
- 「per-line 分割を als_ref 突合」案は**取り下げ**（als_ref に per-line 参照無し）。per-line orientation は下流（kymograph）＋要クリーンデータ。

## 4. 未決 / 繰越

- **trigger_sync finalize（galvo+ALS の 2 mode で先行）**: ① als_datafile gap（then-branch `{type:string}`）② `$id` 確定 ③ `signals.behavior` ④ **`als_datafile_timing` ブロック追加**。resonant は将来枠。
- **per-line orientation/flip**: クリーンな 4-line（calibrated 波形）取得後に線軸射影で判定（multi-line kymograph 前処理）。
- **resonant**: hardware 復帰まで据え置き。
- **NAS（解析/インフラ側）**: Phase 1.5 安全コピー（rename しない・不可逆 in vivo の前に冗長化）。正式移行（#8・命名変換）は一次解析後。archive/proteomics は project 外の単純退避。
- **解析タスク（Track-W）**: ALS の ROI 位置・スキャンパスを 1 Hz 参照画像に overlay（`als_loader.scanfields()` 幾何＋`PIXEL_SIZE_UM`＋figstyle）。
- **commit 候補（今セッション分）**: `als_inject_align.py`・`diag_ttl.py`・in-place の `status.md`／`NEXT_SESSION_kickoff.md`／`handoff_summary_20260608.md`／roadmap 反映（断片）。

## 関連ドキュメント

- 優先順位の正: `in_vivo_water_imaging_brain/docs/strategy_roadmap.md`
- 解析側ログ: `in_vivo_water_imaging_brain/docs/handoff/handoff_summary_20260608.md`
- 取得側 status: `docs/status.md`
- 同期設計: `docs/sync_architecture.md`
- ALS bench 手順: `docs/method_a_als_bench_runsheet_*.md`（親 SOP `sops/method_a_e2e_gonogo_sop.md`）
- 契約 schema: `schemas/trigger_sync.schema.json`
- ツール: `src/python/{datarecorder_loader,als_loader,compare_als_ref,make_trigger_sync,als_inject_align,diag_ttl}.py`
