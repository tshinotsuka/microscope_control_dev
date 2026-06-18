# Status — 取得側（microscope_control_dev）ベンチ進捗

```
更新方法:   この 1 ファイルを in-place 更新（dated にしない）。取得系ベンチ進捗の正本＝これ。
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
scope:      Tier 順・各モダリティの実装状態・次手。設計の正は sync_architecture.md（loose coupling）。
related:    sync_architecture.md / vdaq_io_map.yaml / strategy_roadmap.md / method_a_e2e_gonogo_sop.md
            / method_a_als_bench_runsheet_*.md / trigger_sync.schema.json
            / datarecorder_loader.py / als_loader.py / als_inject_align.py / diag_ttl.py / sweep_quality.py
注:         本稿は 2026-06-18 時点の現行版（galvo go＋ALS go〔single+multi-line/4-line〕／本番前ゲート①=closed・②=PASS／injector を DoTask frame-trigger 化〔WG 廃止〕）。
```

---

## 1. 現在地（2026-06-18）

**2026-06-18 更新（本番前ハードウェアゲート 両方クリア）**

- **ゲート②（deterministic fixed-frame injection）＝PASS**。WG は ALS 下で arm 不安定（後述 §3.5）のため**捨て、injector を D3.2 の raw DoTask（finite・trig `/vDAQ0/D2.2`/rising・`syncArmStart` で acqModeStart auto-arm）で駆動**する v4 に確定。クリーン取り直し 3 run（`run-01_00002`/`00003`/`00004`・4-line・8 ms cycle・1000 cyc・N=500）で **着弾 cycle が 3 run とも #501 で不動**。一方 head_pad は **2.2286 / 1.9838 / 1.1554 s と ~1.07 s（≈134 cycle 分）ばらつく** → host timer なら 134 cycle ズレるところを **frame-clock-trigger が完全に吸収＝決定論成立**。パルスは **150 ms 単発 5.08 V finite**（continuous の永続 on は解消）。`diag_ttl` 全 run 1 edge clean。`N=500 → cycle #501` の **+1 は一定オフセット**（counting 規約・狙うなら `N=目標cycle−1`）。
- **ゲート①（1-min scan stop）＝closed（2026-06-12）**（下記据え置き）。
- → **本番前ハードウェアゲートは①②とも完了**。残りは Tier-0 の契約凍結・SI metadata 実機検証・behavior/injector を契約に載せる（§2.1 / roadmap §4）。**並行で injection GUI**（薄い config 前面＋sanity check・§2.2）を in-vivo 前の打ち間違い防止に。
- 注（cosmetic）: `als_inject_align` の clock 一致が run により 994–1000/1000。head_pad が大きい run で **recorder 窓が scan 末尾の数 cycle を切る**だけ（`run-01_00004` は head_pad 1.15 s で recorder が全 scan を覆い **1000/1000 [OK]**）＝scan は毎回 1000 cyc 完走・**コマ落ちではない**・injection(cycle 501) に無関係。綺麗に [OK] を出したいなら cycle パディング or recorder 余白。

以下 2026-06-12 時点の確定（ゲート① closed の詳細）は据え置き。

- **ゲート①（1-min scan stop）＝closed**。原因は fault ではなく **有限 `hSI.hStackManager.framesPerSlice`**（ALS では cycle 数。総 grab frame = `framesPerSlice × numSlices × numVolumes`。旧「10000/10000 edges」も 166.67 Hz×60 s の programmed 完走で、停止＝正常終了）。実 4-line config で数分連続完走 → `Inf` 化で持続を確認。post-hoc QC `run-02_00001`（4-line・400 s）＝diag_ttl ✓／als_inject_align ✓（49999/50000・residual 2.2426 s・inject cycle #487）／`sweep_quality.py` ✓ **PASS**（50000 cyc・pp ~9.5 一定・decay 無し。4-line は経路が広く 3-line ~4.92 比で妥当）。

以下 2026-06-09 時点の確定（multi-line go）は据え置き。

---

方式A e2e go/no-go：**galvo go ＋ ALS go（single-line ＋ multi-line/3-line・4-line config 取得実績あり）**。3 mode のうち galvo・ALS を確定、resonant は据え置き。

- **galvo 段 go**（既出・16.7 Hz）: ①overflow 無し ②imaging 中も injector TTL を HDF5 記録 ③injector edge と frame_clock が同一 HDF5・同一クロック。t0=4.5012 s／200 frame／median 16.72 Hz／head_pad 1.975 s／inject@frame43。
- **ALS 段 go（single-line・2026-06-08）**: branch A clock 成立＝配線変更ゼロ（既存 `D0.0→AI6` が ALS でも cycle ごとに出る）。residual（ALS head_pad）3.1–3.5 s・可変＝clock で毎回測定。①overflow 無し ②injector TTL が HDF5・device 競合なし（10000/10000 cycle 完走）③`als_datafile_timing` 整列。injector 着弾（run-02_00007・delaySec=6）cycle #2871。
- **ALS multi-line go（3-line・2026-06-09・run-01_00005）**:
  - cycle 6.0 ms（166.67 Hz）・5000 cyc × 3 line = 30.0 s（recorder 32.256 s @ 5000 Hz）。**pause-before-each-line で line skip 無し**（galvo park せず）。
  - ①overflow 無し（5000/5000 cyc 完走）②injector TTL 単発 5V・208.8 ms clean（`diag_ttl`: edges@2.5V=1・frac_high=0.006・high@6.1256 s）・ALS と device 競合なし ③branch A clock `[OK]` 5000/5000 edges @166.67 Hz・**residual（head_pad）=2.1974 s**（前回 3.1–3.5 と別値＝可変・毎 grab clock 測定の設計通り）。
  - injector 着弾: cycle #655（+4.4 ms）。ROI5（pause）着弾は **無害**（t0／cycle 割り当て堅牢・下流整列は per-cycle）。
  - **掃引品質 PASS（multi-line 初）**: `sweep_quality.py` で per-cycle pp 一定（median 4.92／5th 4.904／median/5th=1.00／全 5000 cyc・decay 無し）。旧 run-01_00002 の startup-only park（pp≈0.1）と対照 → **multi-line の per-line 解析が信頼可能**に。

→ sync 正本は galvo＋ALS（single+multi-line）で実機確定。残りは **本番前ゲート 2 件**（§2 最優先）と並行トラック（§2.5）。**resonant は実機不在で据え置き**。

## 2. Tier 順（次手）

- **Tier0（実機・sync 正本）**: galvo ✓ / ALS ✓（single + multi-line/3-line）/ resonant＝据え置き。
- **ALS 4-line**: in vivo は 4-line 想定だが **機構は 3-line で検証済**（cycle-based・line 数非依存）。4 本目取得は ROI GUI Add バグ次第だが**できる見込み＝blocker 扱いしない**（GUI 再現時のみ programmatic builder で回避、保険として用意済・未実行）。

### 2.1 本番前ゲート（最優先・これが通れば実験移行を検討）

1. **1-min scan stop ＝ closed（2026-06-12）**。原因＝有限 `framesPerSlice`（ALS=cycle 数）で fault ではない。`Inf` 化で数分連続取得を確認（4-line `run-02_00001`・post-hoc QC 全 PASS）。
2. **決まったフレームでの投与（fixed-frame injection）＝PASS（2026-06-18）**。host timer（`delaySec`・head_pad 可変）を排し、**injector を D3.2 の raw DoTask（finite・trig `/vDAQ0/D2.2`/rising・`syncArmStart` で acqModeStart auto-arm）で駆動**（WG は ALS 下で arm 不安定のため廃止・§3.5）。3 run（`run-01_00002`/`00003`/`00004`）で head_pad 1.15–2.23 s ばらつきにもかかわらず **着弾 cycle 全て #501**＝決定論成立。150 ms 単発 5.08 V finite・`diag_ttl` clean。`N=目標cycle−1`（+1 オフセット）。**per-frame host UF は overflow ゆえ不可**（§3.5）。

### 2.2 並行トラック（上記と並走）

- **behavior 記録・解析**: Data Recorder（同 vDAQ clock・同 HDF5）に behavior ch を拡張、解析側に取り込み。
- **FastZ 導入**: fast focus を vDAQ clock 同期で ALS／imaging に統合（多深度・volumetric）。
- **データ解析の一本化**: 散在ツール（datarecorder/als loader・compare_als_ref・make_trigger_sync・als_inject_align・diag_ttl・sweep_quality）を raw→sync→per-line→QC の単一パイプラインへ統合。契約＝`trigger_sync.schema.json`。
- **injection／behavior GUI 作成**（in-vivo 前の打ち間違い防止に前倒し可）: `syncControlPanel.m` を起点に **薄い config 前面**（`N`/pulse/enable 入力＋Arm/Disarm＋status・現 cycle rate と計算 delay 表示）。ロジックは UF 側に残す（GUI 落ちても acquisition は無事＝loose coupling）。`N=目標cycle−1`（+1 オフセット）を GUI 内吸収＋sanity check。まず injection 単機能で薄く、behavior 統合は後段。

## 3. behavior 入力経路（Data Recorder）

- Data Recorder を device 追加済。HDF5 出力。**run-config**: Auto Start ON（Grab 同期＝共通 acq-start）／Use Trigger OFF／Sample Rate 5000／Duration Inf。
- **HDF5 レイアウト（確定）**: root group `/` attr `samplerate`（全 ch 共通）／dataset 名 = Recorded Name／float32・MaxSize Inf・ChunkSize／attr `units`/`conversionMultiplier`／**time vector 無し → t = index / samplerate**。
- galvo・ALS とも 4ch 取り込み＋保存を実機確認。**behavior ch 拡張は §2.2 トラックで具体化**。

## 3.5 injector（t0 機構＋fixed-frame＝DoTask v4・PASS 2026-06-18）

- 配線: `D3.2`(injector 出力・**raw DoTask** が駆動) → T 分岐 → `AI7` = Data Recorder で TTL 記録（**t0 正本**）／`D2.1`(Aux・resonant 任意／scanner Aux trigger 1 に loopback・無害)／Legato 本体。frame clock を `D0.0` 出力 → T 分岐 → `AI6`（記録ループバック）＋**`D2.2`（DoTask の Start Trigger 入力）**。
- UF: `acqModeStart`→`syncArmStart`（DoTask を arm）／ `acqAbort`・`acqDone`→`syncDisarm`（line LOW・task クリア）。**`frameAcquired` 空**（overflow 回避の要）。
- t0 = Data Recorder TTL edge を galvo・ALS とも実機確認。scan モード非依存。
- **決定: recorder-start ≠ frame/cycle-0**。head_pad 非ゼロ・**可変**（galvo 1.975 s／ALS 1.15–3.5 s・実測ばらつき）。注入は galvo/resonant=`frame_clock` アンカー／ALS=`als_datafile_timing`（branch A clock）。
- **〜2026-06-09 の旧版（deprecated）**: `syncArmStart` が host timer（`delaySec`）＋ `hWG.writeLineToVal` で発火。head_pad 可変ゆえ **cycle index が run ごとに変わる**（例 #655/#487）＝deterministic でない。
- **2026-06-12 の WG 案は廃止**: WG 'Trig Legato130' を frame clock trigger で…と試みたが、**ScanImage の generic WaveformGenerator は ALS 下で arm 不安定**（`startTask`→`linePeriod` が ALS の `StimulusField` で `isa(...,'ImagingField')` assert に失敗・ErrorHandler が内部例外を握り潰すため `[sync] armed` が false positive になり得る）。continuous で widget Start すれば出力はするが永続 on・finite は不安定。**→ WG をバイパスする方針へ**。
- **2026-06-18 fixed-frame 機構（採用・PASS）＝raw DoTask v4**: `D3.2` 上に **`dabs.vidrio.ddi.rdi.DoTask`（Digital out・finite）** を直接立て、**frame clock(`/vDAQ0/D2.2`/rising) を start trigger** に。`linePeriod` を呼ばないので **ALS 下で素直に start** する。
  - `syncArmStart` が **acqModeStart で auto-arm**（widget 手動 Start 不要）: `createDoTask`/`addChannel`/`cfgSampClkTiming(finite)`/`cfgDigEdgeStartTrig('/vDAQ0/D2.2','rising')`/`writeOutputBuffer`/`start`。
  - 波形: 出力 buffer に **N×cycle の遅延位置へ単発パルス**。実測 `R=100 kHz・nSamp=420000（4.2 s）・~4.000 s 遅延（N=500×8 ms）・150 ms パルス`。
  - 位置決め: `N`（target cycle）で着弾 cycle を指定。**`N=500 → 着弾 cycle #501`（+1 一定オフセット・counting 規約）→ 狙うなら `N=目標cycle−1`**。
  - **検証 PASS（2026-06-18）**: `run-01_00002`/`00003`/`00004`（4-line・8 ms cycle・1000 cyc・N=500）で head_pad 2.2286/1.9838/1.1554 s（~1.07 s≈134 cyc ばらつき）にもかかわらず **着弾 cycle 全て #501**＝決定論成立。150 ms 単発 5.08 V・`diag_ttl` clean。
  - clock 一致（cosmetic）: head_pad が大きい run で recorder 窓が scan 末尾の数 cyc を切り 994–996/1000 [CHECK]・短い run（00004）は 1000/1000 [OK]＝**コマ落ちでなく recorder 末尾切れ**・injection に無関係。
- 物理到達遅延は別途キャリブの定数オフセット（`physical_delay_offset_s`・t0 に折り込まない）。
- **次段（GUI・並行）**: `N`/pulse/enable を入れて arm/disarm する**薄い GUI**（config 前面・ロジックは UF 側・§2.2／`syncControlPanel.m`）。`N=目標cycle−1` を GUI 内吸収＋sanity check で in-vivo 打ち間違い防止。

## 4. 既知の注意

- **1-min scan stop ＝ closed（2026-06-12）**: 原因は fault ではなく **有限 `hSI.hStackManager.framesPerSlice`**（ALS では cycle 数。総 grab frame = `framesPerSlice × numSlices × numVolumes`。166.67 Hz×60 s≈10000 cyc が「10000/10000 edges」運用と符合した通り、停止＝programmed 完走）。実機で `framesPerSlice=60000` 等の有限値を確認 → `Inf` 化で数分連続取得を確認（4-line `run-02_00001`）。**運用**: 取得長 = `cycle_rate × 時間`（trajectory で cycle_rate が変わる）。raster へ切替時は再設定。
- **injector ＝ DoTask v4（fixed-frame・PASS 2026-06-18）**: D3.2 上の raw `DoTask`（finite・trig `D2.2`/rising・`syncArmStart` で acqModeStart auto-arm）。**WG 案は廃止**（WG は ALS 下で `linePeriod` assert により arm 不安定・`[sync] armed` が false positive になり得る）。`N=目標cycle−1`（+1 オフセット）。
- **recorder 末尾切れ（cosmetic・2026-06-18）**: `als_inject_align` の frame clock 一致が run により 994–1000/1000。head_pad が大きい run で recorder 窓が scan 末尾の数 cyc を切るだけ（短 head_pad の `run-01_00004` は 1000/1000 [OK]）＝**コマ落ちでなく recorder 末尾切れ**・scan は毎回完走・injection 無関係。綺麗に [OK] にするなら cycle パディング or recorder 余白。
- **33 Hz overflow（既出）**: 同期 UF は acqModeStart 1 回で per-frame 負荷ゼロ → display/保存側が原因と判断。1-min stop（＝有限 framesPerSlice・解決済）とは別問題。frame rate 上限（~33–50 Hz）は Track-M の dt≤MTT/8 では line-scan で回避。
- **ALS ROI GUI Add バグ（4-line 取得時）**: `ArbitraryLineScanRoiGui>addRoi() (行 77)` → `most.gui.style(uibutton(... 'Add ROI' ...))`。3-line では未発生。回避: SI 再起動／保存 ROI ロード／2-line 複製／programmatic builder（用意済）。再現なら MBF 報告（Optimize Waveform MBF 25850 と束ねる）。
- **掃引品質チェック手順（確立・2026-06-09）**: `sweep_quality.py` で `.scnnr.dat` の per-cycle pp。5th percentile が線サイズ相当（noise floor ~0.1 でない）＝全 cycle 掃引で PASS。startup だけ大きく以降小なら park 病（旧 run-01_00002）。
- **ファイル命名（既出）**: 空 0 KB `_00002` は `hScan2D.logFramesPerFile=Inf` で解消（**per-scanner**・raster へ切替時は要再設定）。`_00001` カウンタは SI 仕様で消せない＝stem 扱い。raster の `_00001_00001.tif` は SI 標準 TIFF 命名。
- **Optimize Waveform 不可（MBF 25850）**: 運用は **Reset Waveform → Calibrate + Test**。
- **ScanImage GUI Table バグ（cosmetic・既出）**: DataRecorderPage 表示ハイライトのみ。記録は正常。

## 5. 解析側への申し送り

> loader は依存軽量（numpy+h5py）で取得 repo `src/python` に single source、解析が一方向 import。schema validation は jsonschema（ivwib）。

- **P1 完了（既出）**: `datarecorder_loader.py` で galvo go 数値確定。
- **P2 完了（single + 2-line exact・既出）**: `compare_als_ref.py` で `als_loader ↔ readLineScanDataFiles` が `max|Δ|=0`。**Track-W B loader read は multi-line まで closed**。`readLineScanDataFiles` は cycle 丸ごとを返し per-ROI に割らない＝per-line orientation は下流（kymograph）。
- **③ harness `als_inject_align.py`（既出）**: branch A/B、residual 算出、`als_datafile_timing` emit。
- **`diag_ttl.py`（既出）**: TTL ch 特徴づけ（injector が AI7 に載っているかの即時切り分け）。
- **`sweep_quality.py`（新規・2026-06-09）**: `.scnnr.dat` の per-cycle 2D pp で掃引品質（park 病検出）。`src/python`・`als_loader` 一方向 import・numpy（plot は matplotlib 任意）。run-01_00005（3-line）で **PASS**。NumPy 2.x 対応（`np.ptp`）。
- **解析一本化（§2.2）**: 上記を単一パイプライン（raw→sync→per-line→QC）へ。詳細は解析側 handoff。
- 解析側ログ詳細: `handoff_summary_20260609.md`。

## 改訂履歴

| 日付 | 変更 |
|---|---|
| 2026-06-18 | **本番前ハードウェアゲート② PASS＝injector を DoTask v4 で deterministic fixed-cycle 化（WG 廃止）**（実機）。WG 'Trig Legato130' は ALS 下で arm 不安定（`startTask`→`linePeriod` が `StimulusField` で assert・ErrorHandler が握り潰し `[sync] armed` が false positive）→ **D3.2 上に raw `dabs.vidrio.ddi.rdi.DoTask`（finite・trig `/vDAQ0/D2.2`/rising）を直接立て**、`linePeriod` を呼ばず ALS 下で素直に start。`syncArmStart` が **acqModeStart で auto-arm**（`createDoTask`/`addChannel`/`cfgSampClkTiming` finite/`cfgDigEdgeStartTrig`/`writeOutputBuffer`/`start`・実測 `R=100kHz・nSamp=420000・~4.000s 遅延・150ms パルス`・widget 手動 Start 不要に）。**検証 PASS**: `run-01_00002`/`00003`/`00004`（4-line・8ms cycle・1000cyc・N=500）で head_pad 2.2286/1.9838/1.1554s（~1.07s≈134cyc ばらつき）にもかかわらず **着弾 cycle 全て #501**＝決定論成立。150ms 単発 5.08V・`diag_ttl` clean。`N=目標cycle−1`（+1 オフセット）。clock 一致 994–1000/1000 は **recorder 末尾切れ**（短 head_pad の 00004 は 1000/1000 [OK]・コマ落ちでない・cosmetic）。→ **本番前ゲート①②とも完了**。次段＝injection GUI（薄い config 前面・打ち間違い防止）＋残り Tier-0（契約・metadata 実機検証・behavior/injector を契約に）。 |
| 2026-06-12 | **本番前ゲート①（1-min scan stop）closed＋②（fixed-frame injection）機構特定（検証残）**（実機）。①: 原因＝有限 `hSI.hStackManager.framesPerSlice`（ALS=cycle 数。総 grab frame=framesPerSlice×numSlices×numVolumes・旧「10000/10000 edges」も 166.67Hz×60s の programmed 完走で fault ではない）→ 実 4-line config で数分連続完走＋`Inf` 持続を確認＝**closed**。post-hoc QC `run-02_00001`（4-line/400s）: diag_ttl ✓／als_inject_align ✓（49999/50000・residual 2.2426s・inject cycle#487）／sweep_quality ✓ PASS（50000cyc・pp~9.5 一定）。②: ScanImage WG 'Trig Legato130'(D3.2) を **frame clock で hardware-trigger** する機構を特定（host timer を排す）。`D0.0`(frame clock out・vDAQgalvo 所有＝WG 予約不可) を**物理 T 分岐で `D2.2` へ** → WG Start Trigger=`/vDAQ0/D2.2`(rising)。**鍵＝WG task は grab 前に widget で Start(arm) が必要**（Apply のみでは無出力）。widget Start→grab で AI7 に clean 単発を記録（`run-06_00005`/`00007`・edges@2.5V=1）。continuous は永続 on で one-shot 不適 → finite 化が必要。**検証残（次回）**: als_inject_align で複数 run の着弾 cycle 一致 → finite 単発化 → 短パルス → `Start=N×cycle` → 複数 run 一致で gate② PASS → `syncArmStart` を acqModeStart-arm 版へ。配線 `vdaq_io_map.yaml` に D0.0→D2.2 追加。WG widget の SceneTree replaceChild storm は GUI ノイズ（出力に無関係）。 |
| 2026-06-09 | **方式A ALS go を multi-line（3-line）へ拡張**（run-01_00005）。cycle 6.0ms/166.67Hz・5000cyc×3line=30s。①overflow無 ②injector 単発5V 208.8ms clean・競合無 ③branch A clock [OK] 5000/5000・residual 2.1974s。injector cycle#655 着弾（ROI5 pause＝無害）。pause-before-each-line で line skip 無し。**掃引品質 PASS**（新ツール `sweep_quality.py`: per-cycle pp median 4.92・5th 4.904・全cyc安定＝park病なし）。次フェーズ戦略反映: 最優先＝①1-min stop 原因探索＋改善 ②決まったフレーム投与（clock/frame-trigger 化）→通れば実験移行。並行＝behavior 記録解析・FastZ 導入・解析一本化・injection/behavior GUI。4-line はできる見込みで skip、より速い ALS は次回最適化案。 |
| 2026-06-08 | **方式A ALS go（single-line）**。branch A clock 成立（配線変更ゼロ）。residual 3.1–3.5s 可変＝毎 grab 測定。injector AI7 path 修正（単発5V）・`delaySec>head_pad`（=6）で cycle 着弾。新ツール `als_inject_align.py`・`diag_ttl.py`。P2 2-line exact＝Track-W B loader closed。resonant 据え置き→finalize 2 mode 化。`logFramesPerFile=Inf`（per-scanner）。4-line は ROI GUI バグで未完。 |
| 2026-06-06 | 解析側 P2（single-line exact）・trigger_sync emitter（galvo `.h5` で schema VALID）。jsonschema を ivwib へ。 |
| 2026-06-05 (b) | P1: galvo go 数値確定。決定: recorder-start≠frame-0／frame_clock anchor／median rate。trigger_sync schema draft 化。 |
| 2026-06-05 (a) | 方式A e2e **galvo go**。Data Recorder 配線・run-config・UF 登録・HDF5 レイアウト確定・受け入れ ①②③。 |
