# Status — 取得側（microscope_control_dev）ベンチ進捗

```
更新方法:   この 1 ファイルを in-place 更新（dated にしない）。取得系ベンチ進捗の正本＝これ。
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
scope:      Tier 順・各モダリティの実装状態・次手。設計の正は sync_architecture.md（loose coupling）。
related:    sync_architecture.md / vdaq_io_map.yaml / strategy_roadmap.md / method_a_e2e_gonogo_sop.md
            / trigger_sync.schema.json / datarecorder_loader.py
注:         本稿は 2026-06-05 時点の現行版（galvo go＋解析側 P1/P3 反映）。
            既存 status.md と §2/§3/§3.5 の構造を突き合わせて in-place マージ（prior content を失わない）。
```

---

## 1. 現在地（2026-06-05）

方式A e2e go/no-go：**galvo 段 go**（実機 16.7 Hz で ①overflow 無し ②imaging 中も injector TTL を HDF5 記録・4ch 取り込み＋保存可 ③injector edge と frame_clock が同一 HDF5・同一クロック）。
**解析側でも数値確定**（`datarecorder_loader.py`）: samplerate 5000／両 ch／t0=4.5012 s 単一エッジ／frame_clock 200=設定 frames／**median rate 16.72 Hz=設定 16.7**／head pad 1.975 s・tail 0.035 s／inject @ frame 43。
→ 残りは **ALS 並走 → resonant 並走**（次手）。3 mode 揃えば `trigger_sync` schema を finalize。

## 2. Tier 順（次手）

- **Tier0 残（実機）**: ① **ALS に載せる**（次回の単一ヘッドライン）＝ Data Recorder＋injector が ALS と device 競合せず並走し HDF5 に TTL が載るか。② resonant 並走。
- **随時**: 33 Hz overflow の A/B（§4）。frame vs line-scan（Track-M）の判断材料。
- **本番前**: Data Recorder の File Directory を imaging と同 stem（`raw/`）へ。今は temp_data_recorder。
- **3 mode 揃い → `trigger_sync.schema.json` を finalize**（version up・`signals.behavior` 追加・`$id` 確定）。

## 3. behavior 入力経路（Data Recorder）

- Data Recorder を device 追加済。HDF5 出力。**run-config**: Auto Start ON（Grab 同期＝共通 acq-start）／Use Trigger OFF／Sample Rate 5000（実下限 3052 Hz）／Duration Inf。
- **HDF5 レイアウト（確定）**: root group `/` attr `samplerate`（全 ch 共通）／dataset 名 = Recorded Name／float32・MaxSize Inf・ChunkSize 50000・attr `units`/`conversionMultiplier`／**time vector 無し → t = index / samplerate**。
- 16.7 Hz で 4ch 取り込み＋保存を demo 済。

## 3.5 injector（acqModeStart 単発・t0 機構）

- 配線: `D3.2`(WG) → T 分岐 → `AI7` = Data Recorder で TTL 記録（**t0 正本**）／`D2.1`(Aux・resonant 任意)／Legato 本体。frame clock を `D0.0` 出力 → `AI6`。
- UF: `acqModeStart`→`syncArmStart` ／ `acqAbort`・`acqDone`→`syncDisarm`。**`frameAcquired` 空**（overflow 回避の要）。
- **galvo で t0 = Data Recorder TTL edge を実機確認**。ALS/resonant 残。
- **決定（2026-06-05 実測）: recorder-start ≠ frame-0**。Auto-Start は frame 1 より前から録るため **head pad 非ゼロ**（1.975 s @ galvo）。→ 注入は **`frame_clock` にアンカー（galvo/resonant）／ALS は `als_datafile_timing`**。**recorder-start にはアンカーしない**。frame rate は **median 間隔**から（`n/total` は希釈）。
- 注入タイミングは任意・**t0 は実エッジの記録値＝時間ゼロ**。物理到達遅延は別途キャリブの定数オフセット（`physical_delay_offset_s`・t0 に折り込まない）。

## 4. 既知の注意

- **33 Hz overflow**: 同期 UF は acqModeStart 1 回で per-frame 負荷ゼロ → 原因は display/保存側と判断（既知 ~33–50 Hz 上限と整合）。**A/B 未**: acqModeStart UF を disable して 33 Hz Grab／display 負荷を下げて再 Grab。
- **ScanImage GUI バグ（cosmetic）**: `DataRecorderPage/cellEdited`→`highlightTableRows` が `matlab.ui.control.Table` 型で落ちる。Status OK・記録正常＝表示ハイライトのみ。MATLAB 2026.0 は 2025b+ 必須。MBF バンドル候補。signal セル再編集しない運用で回避。
- **コード註陳腐化（小）**: `legatoInjectStart.m`/`syncArmStart.m` の「real edge は D2.1 Aux loopback」は旧モデル。t0 正本は Data Recorder TTL edge。コメント 1 行更新のみ。

## 5. 解析側への申し送り（後で修正可）

> 解析環境 = 解析 PC / オフライン PC（ivwib env）。取得 PC には ivwib を複製せず極小 quicklook env のみ。loader は依存軽量（numpy+h5py）で取得 repo に single source、解析が一方向 import。

- **P1 完了**: `datarecorder_loader.py`（`src/python/`・`als_loader.py` の隣）が動作、**galvo go を数値確定**（上記 §1 の数値）。loader は frame rate を median 間隔から算出＋head/tail padding 報告。
- **P3 draft 完了**: `trigger_sync.schema.json`（draft 2020-12・`als_sidecar.schema.json` の兄弟・galvo worked example・検証済・条件分岐で scan_mode↔anchor 強制）。doc 反映断片＝`trigger_sync_doc_notes.md`。**finalize は ALS/resonant 並走＋behavior ch 確定後**。
- **P2（次）**: `als_loader` vs MATLAB `readLineScanDataFiles` 突合（offset pre/post・bidirectional・feedback ×12.5）。**要: rig で `als_ref_*.mat` を export**（Monitor Scanner Feedback ON の acquisition）。それまで offline は als_loader 単体＋比較ハーネスまで。二重計上しない（取得側 Tier1 #4）。
- **P4（bench 後）**: 統合 unified timebase（ALS imaging＋sync `.h5` を 1 本へ・注入 t0 基準に整列）。
- 解析側ログ詳細: `handoff_summary_20260605b.md`。

## 改訂履歴

| 日付 | 変更 |
|---|---|
| 2026-06-05 (b) | 解析側 P1/P3 反映: `datarecorder_loader.py` で galvo go を数値確定（16.72 Hz=設定／t0=4.5012 s／inject@frame43／head pad 1.975 s）。**決定: recorder-start≠frame-0／frame_clock anchor／median rate**（§3.5）。`trigger_sync.schema.json` draft 化（galvo worked example・検証済）。§5 申し送りを P1 完了・P3 draft・P2 次へ更新。 |
| 2026-06-05 (a) | 方式A e2e **galvo go**。Data Recorder device 追加・配線（AI7=injector t0／AI6=frame_clock←D0.0）・run-config（Auto Start ON）・UF 登録（acqModeStart 単発・frameAcquired 空）。HDF5 レイアウト確定（root `samplerate`／Recorded Name dataset／float32 拡張 chunk／t=idx/fs・実下限 3052 Hz→5000 採用）。受け入れテスト→16.7 Hz Grab で ①②③。33 Hz overflow=display-bound 仮説。ScanImage Table バグ cosmetic。 |
