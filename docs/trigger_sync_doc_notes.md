# trigger_sync — doc 反映用 prose 断片（参照＋決定のみ）

> schema 本体は `trigger_sync.schema.json`（解析 repo・`als_sidecar.schema.json` の隣）。
> 以下は prose 側に貼る「参照＋決定」だけ。構造は schema が正、ここは名前参照に留める（loose coupling）。

---

## → `sync_architecture.md` §2（同期の正本・契約）に追記

- **`trigger_sync` schema を draft 化（galvo 実データを worked example に）**。実体＝解析 repo の `trigger_sync.schema.json`（draft 2020-12・`als_sidecar.schema.json` の兄弟）。per-acquisition の sync sidecar を validate する。
- **決定（2026-06-05・galvo 実測）: recorder-start ≠ frame-0。** Data Recorder の Auto-Start は frame 1 より前から録り出すため **head pad は非ゼロ**（実測 1.975 s @ galvo 16.72 Hz・tail 0.035 s）。よって**注入は `frame_clock` に対してアンカーする（galvo/resonant）／ALS は common acq-start＋ALS data-file timing**。**recorder-start に対してはアンカーしない**。
- frame rate は **フレーム間隔の中央値**から取る（`n_frames / total_duration` ではない・余白で希釈されるため）。
- t0 正本は従来どおり **Data Recorder の injector TTL エッジ**（scan モード非依存・2026-06-04 の決定）。`t0_recorder_s` は時間ゼロだが imaging との対応は `anchor` 経由で取る。
- 物理到達遅延は **t0 とは別の較正定数**（schema では `physical_delay_offset_s`・下流で加算・t0 に折り込まない）。

## → `status.md` §5（解析側申し送り）の更新

- **P1 完了**: `datarecorder_loader.py` が動作、**galvo go を数値で確定**（median 16.72 Hz = 設定 16.7／t0=4.5012 s・単一エッジ／inject @ frame 43・head pad 1.975 s）。
- **`trigger_sync.schema.json` を draft 化**（galvo 実例つき・条件分岐で scan_mode↔anchor を強制）。finalize は **ALS/resonant 並走＋behavior ch 確定**の後。
- 次: **P2**（als_loader vs `als_ref_*.mat` 突合・rig で参照 export 後）／**ALS bench**（次回 rig ヘッドライン）。

## → `strategy_roadmap.md` §3（契約・同期正本）に反映（もんでから）

- 契約の実体＝`trigger_sync.schema.json` を §3 から名前参照。galvo 段で「root `samplerate`＋Recorded Name dataset＋t=idx/fs＋frame_clock anchor＋head offset 非ゼロ」を実証済み。3 mode 並走後に schema を finalize。
