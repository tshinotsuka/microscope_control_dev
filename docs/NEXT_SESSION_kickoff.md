# 次セッション kickoff（貼り付け用）

## A. 次回チャットに添付するファイル（優先順）

**必須（これだけでも resume 可）**
1. `handoff_summary_20260605b.md` — セッションログ＋次手（master ポインタ）
2. `status.md` — 取得側ベンチ進捗の正

**設計・wiring の正本（rig 作業なら必須）**
3. `sync_architecture.md` — 同期設計の正（recorder-start≠frame-0／frame_clock anchor）
4. `vdaq_io_map.yaml` — wiring の正（AI7/D0.0/AI6 confirmed）
5. `method_a_e2e_gonogo_sop.md` — ベンチ手順（ALS 節を使う）

**契約・コード（解析・schema 作業なら必須）**
6. `trigger_sync.schema.json` — 契約 draft（galvo worked example）
7. `datarecorder_loader.py` — `.h5` consumer

**あれば**
8. `strategy_roadmap.md` — 優先順位の単一の正
9. `als_loader.py`（repo）＋ `als_ref_*.mat`（rig export 後・P2 用）

> minimal で start するなら 1,2＋（rig なら 3,4,5／解析なら 6,7）。

## B. 貼り付け用 kickoff プロンプト

```
【前回の続き — 方式A e2e／trigger_sync】

状況: 方式A end-to-end の galvo 段は go（数値確定済み）。injector t0 = Data Recorder の
TTL エッジ(AI7)、frame clock = D0.0→AI6 で記録、recorder-start≠frame-0 なので注入は
frame_clock にアンカー。trigger_sync.schema.json は galvo worked example つきで draft 済み。

添付（正本）: handoff_summary_20260605b.md / status.md / sync_architecture.md /
vdaq_io_map.yaml / trigger_sync.schema.json / datarecorder_loader.py /
method_a_e2e_gonogo_sop.md。

次の単一ヘッドライン = ALS bench（rig）:
ALS モードで Data Recorder＋injector を並走させ、(1) device 競合なく HDF5 に injector TTL が
載るか、(2) als_datafile_timing で整列できるか、を確認。続けて resonant も。
あわせて rig で als_ref_*.mat を export（Monitor Scanner Feedback ON の ALS acquisition・
scanimage.util.readLineScanDataFiles）→ オフラインで P2（als_loader vs 参照突合:
offset pre/post・bidirectional・feedback ×12.5）。3 mode 揃ったら trigger_sync.schema.json を
finalize（version up・signals.behavior 追加・$id 確定）。

まず ALS bench を method_a_e2e_gonogo_sop.md に沿って手順整理して、step by step で進めよう。
```

## C. 区切り前に commit しておく（repo を整合させる）

- `src/ivwib/__init__.py`（#7 skeleton・editable install 開通）
- `pyproject.toml` の `h5py`/`scipy` 追記
- `datarecorder_loader.py`（取得 repo `src/python/`）
- `trigger_sync.schema.json`（解析 repo・`als_sidecar.schema.json` の隣）
- `sync_architecture.md` / `vdaq_io_map.yaml` の更新版（取得 repo）
- `status.md`（取得 repo）/ `handoff_summary_20260605b.md`（解析 repo）
- `trigger_sync_doc_notes.md` の §2/§5/§3 反映（sync_architecture/status/roadmap へ）
