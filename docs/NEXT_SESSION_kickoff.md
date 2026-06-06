# NEXT SESSION kickoff — 取得側（次回＝実機あり）

```
last_updated:   2026-06-06
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
reflects:       handoff_summary_20260606.md（解析側ログ・本 kickoff はその前向き要約）
scope:          次セッション（実機あり）の頭出し。オフラインで閉じた分は「済」、実機ゲート分を順序づけ。
                状態の正本＝status.md / roadmap。本 doc は「次に何を・どの順で」だけ。
```

> 起動時: 古い kickoff を current 扱いしない。`last_updated` を確認。状態は status.md / roadmap が正。

---

## 0. いまの地点（1 段落）

方式A **galvo go**（取得・解析とも数値確定）。実機停止中のオフラインで **P2（als_loader ↔ readLineScanDataFiles）を single-line で exact 完了**、**als_loader patch**（`feedback_on_pmt_grid`・`pmt_to_volts` の offset 解消）、**trigger_sync emitter＋validator** を galvo 実データで通した（schema VALID・worked example ビット再現）。**残りは全部実機ゲート**。

## 1. 次セッションでやること（実機・優先順）

1. **ALS bench（単一ヘッドライン）** ＝ `method_a_als_bench_runsheet`（親 SOP `method_a_e2e_gonogo_sop.md`）。go/no-go: ① overflow 無し ② injector TTL が Data Recorder HDF5 に載る（**ALS と device 競合なし**）③ **`als_datafile_timing` で整列**。**③ の核心 = recorder-start と ALS 取得開始の residual offset（galvo の head_pad 1.975 s に相当）を数値化**。OFF で競合切り分け → ON（Monitor Scanner Feedback）で als_ref＋sync 同録りが理想。
2. **run-02（2-line）の `als_ref_*.mat` を export**（Monitor Scanner Feedback ON）→ オフラインで `compare_als_ref.py` を **`segment_samples` で line 割り**して multi-line の **bidirectional / segmentation** を閉じる ＝ **Track-W B 完**（single-line は済）。
3. **resonant bench** ＝ frame_clock 再有効（D0.0→AI6）＋ `D2.1` Aux→TIFF timestamp の任意クロスチェック。
4. **3 mode 揃い → `trigger_sync.schema.json` finalize**: version up・`signals.behavior` 追加・`$id` 確定（placeholder `yasuilab.example` → als_sidecar 規則）・**schema gap 修正**（als then-branch で `als_datafile: {type: string}` ＝ null を弾く）。

## 2. 実機前チェック（preflight）

- ALS: **Optimize Waveform はベンダーバグ(MBF 25850)で不可 → Reset Waveform で raw command AO**。`als_ref` を取る回は **Monitor Scanner Feedback ON**（`.scnnr.dat` 実位置が真値）。
- Data Recorder: Sample Rate **5000 Hz**（galvo と同値・比較可）、Auto Start ON、Use Trigger OFF、Duration Inf。**本番前に File Directory を temp_data_recorder → `raw/`（imaging と同 stem）**。
- UF: `acqModeStart→syncArmStart` / `acqAbort・acqDone→syncDisarm` / **`frameAcquired` 空**（overflow 回避の要）。
- 注入は `delaySec`（ALS は targetFrame 使わない）。

## 3. オフラインで既に閉じた（次回やり直さない）

- `als_loader.py`：readLineScanDataFiles と **exact**（single-line・2 acq・PMT 生 counts/scanner G native とも `max|Δ|=0`）。**on-disk PMT＝生 int16・pre-offset**（`subtract_offset=False` 忠実）。`feedback_on_pmt_grid()` 実装（×12.5＝rate 比・非整数補間）。
- `compare_als_ref.py`（P2 ハーネス・interp×orient joint）・`make_trigger_sync.py`（emitter＋validator）：合成 fixture＋実 galvo で検証済。
- `galvo_sidecar.json`：実 `.h5` から emit・schema VALID。**取得 repo の該当 acq 隣 / `raw/` へ移動して commit**（今は解析 repo ルートに出ている）。
- docs：status §5 / roadmap §2・§4 / handoff_20260606 反映済。

## 4. 未決 / 繰越

- **trigger_sync 未決（finalize 時に一括）**: schema gap（als_datafile null 通過）・`$id` placeholder・`signals.behavior` 未追加。3 mode 並走後。
- **multi-line（2-line）未検**: run-02 の als_ref 待ち（上 §1-2）。
- **#7 `src/ivwib` 実コード移行**: skeleton で install は開通済、`import ivwib` は今は空。
- **0604b 繰越 §2-2**: cell24/29 を実データ再実行（Track-M・正しい kernel）。
- **commit 候補（今セッション分）**: `als_loader.py`・`compare_als_ref.py`・`make_trigger_sync.py`・`galvo_sidecar.json`・`handoff_summary_20260606.md`・in-place の `status.md`/`strategy_roadmap.md`・`pyproject.toml`（jsonschema 追記）。

## 関連ドキュメント

- 優先順位の正: `in_vivo_water_imaging_brain/docs/strategy_roadmap.md`（§2 ミラー・§4 Track-W B・§5 gate）
- 解析側ログ: `in_vivo_water_imaging_brain/docs/handoff/handoff_summary_20260606.md`
- 取得側 status: `docs/status.md`（§2 Tier 順・§3.5 injector・§5 解析申し送り）
- 同期設計: `docs/sync_architecture.md`
- ALS bench 手順: `docs/method_a_als_bench_runsheet_*.md`（親 SOP `sops/method_a_e2e_gonogo_sop.md`）
- 契約 schema: `schemas/trigger_sync.schema.json`（draft v0.1.0）／反映断片 `docs/trigger_sync_doc_notes.md`
- ツール: `src/python/{als_loader,datarecorder_loader,compare_als_ref,make_trigger_sync}.py`
