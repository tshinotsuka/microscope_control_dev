# Status — 取得側（microscope_control_dev）ベンチ進捗

```
更新方法:   この 1 ファイルを in-place 更新（dated にしない）。取得系ベンチ進捗の正本＝これ。
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
scope:      Tier 順・各モダリティの実装状態・次手。設計の正は sync_architecture.md（loose coupling）。
related:    sync_architecture.md / vdaq_io_map.yaml / strategy_roadmap.md / method_a_e2e_gonogo_sop.md
            / method_a_als_bench_runsheet_*.md / trigger_sync.schema.json
            / datarecorder_loader.py / als_loader.py / als_inject_align.py / diag_ttl.py
注:         本稿は 2026-06-08 時点の現行版（galvo go＋ALS go＋解析側 P1/P2/P3 反映）。
```

---

## 1. 現在地（2026-06-08）

方式A e2e go/no-go：**galvo go ＋ ALS go**（いずれも実機で数値確定）。

- **galvo 段 go**（既出・16.7 Hz）: ①overflow 無し ②imaging 中も injector TTL を HDF5 記録 ③injector edge と frame_clock が同一 HDF5・同一クロック。t0=4.5012 s／200 frame／median 16.72 Hz／head_pad 1.975 s／inject@frame43。
- **ALS 段 go（2026-06-08・single-line）**:
  - **branch A clock 成立＝配線変更ゼロ**。既存 `D0.0→AI6` frame-clock-out が **ALS でも cycle ごとに出る**（各 cycle＝内部 "frame"）。`als_inject_align.py` が `frame_clock` を ALS cycle clock として検出 `[OK]`（run-02_00003: 500 Hz・2ms cycle／run-02_00007: 1000 Hz・1ms cycle・いずれも 10000/10000 edges）。
  - **residual offset（ALS head_pad）を毎 grab 測定**: 3.4856 / 3.1302 / 3.2608 s（**可変**。固定値で仮定せず clock から毎回取る）。
  - ①overflow 無し ②injector TTL が HDF5・**ALS と device 競合なし**（10000/10000 cycle 完走）③`als_datafile_timing` 整列＝branch A clock で達成。
  - **injector 着弾確認（run-02_00007・delaySec=6）**: cycle #2871 に着弾。TTL は単発 5V・218.6 ms（clean）。

→ **3 mode のうち galvo・ALS の 2 つが確定**。**resonant は実機不在で据え置き**（§2）。残りは finalize と in vivo gate 準備（§5）。

## 2. Tier 順（次手）

- **Tier0（実機）**: galvo ✓ / **ALS ✓（single-line）** / **resonant＝据え置き（hardware 無し・今は無視）**。
- **ALS multi-line（in vivo は 4-line 想定）**: **4-line grab が ScanImage の ROI GUI バグで未完**（§4）。loader 検証自体は 2-line で済（§5）。実機復帰時に GUI バグを解消して 4-line を取得。
- **本番前**: Data Recorder File Directory を imaging と同 stem（`raw/`）へ。`logFramesPerFile=Inf`（§4）。
- **finalize（2 mode で先行可）**: resonant 据え置きにより「3 mode 揃い」を **galvo+ALS の 2 mode finalize** に縮小。resonant は将来枠。`trigger_sync.schema.json` を version up・`signals.behavior` 追加・`$id` 確定・**`als_datafile_timing` ブロック追加**・**als then-branch の als_datafile gap 修正**。

## 3. behavior 入力経路（Data Recorder）

- Data Recorder を device 追加済。HDF5 出力。**run-config**: Auto Start ON（Grab 同期＝共通 acq-start）／Use Trigger OFF／Sample Rate 5000／Duration Inf。
- **HDF5 レイアウト（確定）**: root group `/` attr `samplerate`（全 ch 共通）／dataset 名 = Recorded Name／float32・MaxSize Inf・ChunkSize／attr `units`/`conversionMultiplier`／**time vector 無し → t = index / samplerate**。
- galvo・ALS とも 4ch 取り込み＋保存を実機確認。

## 3.5 injector（acqModeStart 単発・t0 機構）

- 配線: `D3.2`(WG) → T 分岐 → `AI7` = Data Recorder で TTL 記録（**t0 正本**）／`D2.1`(Aux・resonant 任意)／Legato 本体。frame clock を `D0.0` 出力 → `AI6`。
- UF: `acqModeStart`→`syncArmStart` ／ `acqAbort`・`acqDone`→`syncDisarm`。**`frameAcquired` 空**（overflow 回避の要）。
- t0 = Data Recorder TTL edge を **galvo・ALS とも実機確認**。scan モード非依存。
- **決定: recorder-start ≠ frame/cycle-0**。head_pad 非ゼロ（galvo 1.975 s／**ALS 3.1–3.5 s・可変**）。注入は **galvo/resonant=`frame_clock` アンカー／ALS=`als_datafile_timing`（branch A clock）**。recorder-start にはアンカーしない。
- **ALS は `delaySec` 指定（`targetFrame` 不使用）。決定（2026-06-08）: `delaySec > head_pad` が必須**。`delaySec=2` は head_pad（~3.13 s）内に落ちて cycle に乗らなかった → **`delaySec=6` 採用**で cycle 着弾。head_pad の原因（シャッター等）は不問＝着弾 cycle は clock で毎回測る。
- 物理到達遅延は別途キャリブの定数オフセット（`physical_delay_offset_s`・t0 に折り込まない）。

## 4. 既知の注意

- **33 Hz overflow**: 同期 UF は acqModeStart 1 回で per-frame 負荷ゼロ → display/保存側が原因と判断。A/B 未。
- **ALS ROI GUI バグ（4-line 取得の blocker・2026-06-08）**: 4 本目の ROI 追加で `scanimage.gui.ArbitraryLineScanRoiGui>addRoi() (行 77)` → `most.gui.style(uibutton(... 'Add ROI' ...))` → `executeUserCallback` でエラー。**sync コードは無関係**（console で injector arm/ON/OFF 正常）。root メッセージは未取得（MATLAB を閉じた）。MATLAB R2025b と SI GUI styling の相性疑い＝**ベンダー GUI バグ候補（Optimize Waveform MBF 25850 と束ねて報告）**。回避: SI 再起動／保存 ROI group ロード／programmatic ROI／root エラー取得（`disp(lasterr)`）。
- **ファイル命名（一部解決・2026-06-08）**: ALS は `[stem][file counter].meta.txt/.pmt.dat/.scnnr.dat`（**`_00001` カウンタは SI 仕様・消せない＝stem に含めて扱う**）。空の 0 KB `_00002` はロール由来 → **`hScan2D.logFramesPerFile = Inf` で解消**（ALS で確認）。**`logFramesPerFile` はスキャナごと**: raster へ切替時は別スキャナなので未設定だと再発しうる。raster の `_00001_00001.tif`（二重番号）は **SI 標準 TIFF 命名 `<base>_<acq>_<file>.tif`・実データあり＝空ファイル問題ではない**。空 raster が出たら raster スキャナでも Inf。
- **旧 ALS データの掃引品質（2026-06-08 発見）**: `20260601 cond-cagegfpfixed run-01_00002`（fixed sample 試験）の scanner feedback は **startup cycle 0–4 だけ掃引、以降は線内 pp≈ノイズ（0.08–0.13）で galvo がほぼ park・mean 位置ドリフト**（pp>1 は 358/5000 cycle のみ）。**galvo が線パスをトレースしていない回**（Optimize Waveform 未最適化＝MBF 25850 の線が濃厚）。loader 検証（§5）は exact で無関係に成立するが、**per-line 解析には不適**。→ 最近の grab（Reset/Calibrate 運用後）が毎 cycle 掃いているかを `.scnnr.dat` の cycle 別 pp で要確認（実験品質チェック）。
- **ScanImage GUI Table バグ（cosmetic・既出）**: DataRecorderPage の表示ハイライトのみ。記録は正常。

## 5. 解析側への申し送り

> loader は依存軽量（numpy+h5py）で取得 repo `src/python` に single source、解析が一方向 import。取得 PC は極小 quicklook env（numpy+h5py）で go/no-go ③ をその場確認可。schema validation は jsonschema（ivwib）。

- **P1 完了（既出）**: `datarecorder_loader.py` で galvo go 数値確定（median 16.72 Hz／t0 4.5012／head_pad 1.975／inject@frame43）。
- **P2 完了（single-line exact・既出 ＋ 2-line も exact・2026-06-08）**: `compare_als_ref.py` で `als_loader ↔ readLineScanDataFiles`。**run-01_00002（2-line・bidi ON・feedback）でも PMT raw_counts `max|Δ|=0`／scanner native as_is `max|Δ|=0`**。cycle 単位 bidi は `as_is`（反転不要・single-line と同結論）。**Track-W B の loader read は multi-line も含めて closed**。
  - **重要（プラン訂正）**: `readLineScanDataFiles` は cycle 丸ごとを返し **per-ROI に割らない**ため、「per-line 分割を als_ref と突合」は**比較対象が無く成立しない**＝当初プラン取り下げ。
  - **per-line orientation/flip は下流（kymograph）の話**で loader gate ではない。線は傾く（ROI 1 rot 10°／ROI 2 rot 345°）→ 線軸へ射影して判定。**run-01_00002 は掃引品質不良（§4）で測れない** → クリーンな multi-line（in-vivo 4-line・calibrated 波形）で実施。
- **P3 emitter 済（既出）＋ ③ harness 新規（2026-06-08）**: `als_inject_align.py`（`src/python`・両 loader を一方向 import・numpy+h5py のみで動作）。Data Recorder `.h5`＋ALS `.meta.txt` から **injector t0 を ALS timeline に整列**、**residual offset（ALS head_pad）を算出**。branch A（clock loopback・測定）／branch B（common acq-start 近似・residual 不可測で cycle 不確かさ ~head_pad/T_cyc を警告）の両分岐。`als_datafile_timing` ブロックを emit（schema finalize 時に取り込む）。実 galvo `.h5`＋合成 fixture（per-cycle/per-line/flat）＋実 ALS で検証済。
- **`diag_ttl.py` 新規（2026-06-08）**: Data Recorder の TTL ch を特徴づけ（edge 数・周期性・最長 HIGH 区間・VERDICT）。AI7 が injector TTL を載せているかの即時切り分け用（今回 AI7 path 不通＝flat mV ノイズを検出 → path 修正で単発 5V に復旧）。
- **resonant 据え置き**: schema finalize は galvo+ALS の 2 mode で先行（resonant は将来枠）。
- 解析側ログ詳細: `handoff_summary_20260608.md`。

## 改訂履歴

| 日付 | 変更 |
|---|---|
| 2026-06-08 | **方式A ALS go（single-line）**。branch A clock 成立＝既存 D0.0→AI6 が ALS cycle clock を載せる（配線変更ゼロ）。residual（ALS head_pad）3.1–3.5 s・可変＝clock で毎回測定。injector: AI7 path 不通を `diag_ttl.py` で検出→修正（単発 5V）／**`delaySec > head_pad` 必須＝`delaySec=6` で cycle 着弾**。新ツール `als_inject_align.py`（③ harness）・`diag_ttl.py`。**P2 を 2-line でも exact**（run-01_00002・`max|Δ|=0`）＝Track-W B loader closed（multi-line 含む）。「per-line 分割を als_ref 突合」案は取り下げ（als_ref に per-line 参照無し）。per-line orientation は下流＋要クリーンデータ（旧 run-01_00002 は掃引不良）。**resonant 据え置き**→finalize を 2 mode 化。ファイル命名 `logFramesPerFile=Inf`（per-scanner）。4-line は ROI GUI バグで未完。 |
| 2026-06-06 | 解析側 P2（single-line exact）・als_loader patch・trigger_sync emitter（galvo `.h5` で schema VALID・worked example 再現）。jsonschema を ivwib pyproject へ。 |
| 2026-06-05 (b) | P1: datarecorder_loader で galvo go 数値確定。決定: recorder-start≠frame-0／frame_clock anchor／median rate。trigger_sync schema draft 化。 |
| 2026-06-05 (a) | 方式A e2e **galvo go**。Data Recorder 配線・run-config・UF 登録・HDF5 レイアウト確定・受け入れ ①②③。 |
