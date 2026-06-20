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
- → **本番前ハードウェアゲートは①②とも完了**。残りは Tier-0 の契約凍結・SI metadata 実機検証・behavior/injector を契約に載せる（§2.1 / roadmap §4）。**injection GUI v1 完了（2026-06-18・`syncControlPanel`・§2.2/§3.5）**＝in-vivo 前の打ち間違い防止。**R1 sidecar VALID＝PASS（2026-06-19・gate 条件2 の契約 emission 部 closed）**／**cycle_period は hSI 自動取得（`hRoiManager.scanFramePeriod`）で done（2026-06-19）**。残 gate 条件2＝SI 自動 metadata の実機 SOP 検証のみ（**C2 behavior を契約に closed＝2026-06-20・schema 0.3.0 `recorded_channels`・実 ALS VALID**／**C1 pixel-size＝`objectiveResolution=15` 未校正の摘発・MDF 34.4 校正 pending〔実機〕**）。
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
- **injection GUI v1 ＝完了（2026-06-18・`syncControlPanel`）**: appdata 契約（`sync_v4_params`/`sync_v4_armed`/`sync_v4_task`）の上に **薄い config 前面**（`N`/pulse/`R`/cycle period 入力＋Arm/Disarm＋armed ランプ＋直近 inject_cycle・計算 delay/nSamp を自動表示）。**ドック可能モジュール**（親コンテナ引数で将来ダッシュボードに埋込可）。ロジックは UF 側に残す（GUI 落ちても acquisition は無事＝loose coupling）。`N=目標cycle−1`（+1 オフセット）は表示で吸収。実機で N 設定・arm/disarm・ランプ動作確認済。**cycle period は hSI 自動取得（`hRoiManager.scanFramePeriod`・`alsCyclePeriodS` 単一正本）で done（2026-06-19）**＝silent-misconfig 解消（override が live とズレれば arm 時 warn）。behavior 統合は後段。

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
  - `syncArmStart` が **acqModeStart で auto-arm**（widget 手動 Start 不要）。**確定シーケンス（2026-06-18 実機）**: `hDAQ=ResourceStore().filterByName('vDAQ0')`(=vDAQR1) → `createDoTask` / `addChannel('D3.2',…,0)`（init 0=idle LOW）/ `convertToBufferedTask`（on-demand→buffered・必須）/ `sampleRate=R_Hz`（property）/ `sampleMode='finite'` / `samplesPerTrigger=nSamp` / `writeOutputBuffer` / `cfgDigEdgeStartTrig('/vDAQ0/D2.2')`（edge=rising 既定）/ `start`。
  - **罠3点**: (a) **`cfgSampClkTiming(rate)` は 'not done' で落ちる → `sampleRate` property 直叩きで代替**（当初メモの `cfgSampClkTiming(finite)` は不可）。(b) **`sampleMode` 既定は 'continuous' → 'finite' を明示しないと buffer がループ**。(c) Vidrio クラスは `.p`（ソース不可）→ `methods('dabs.vidrio.ddi.rdi.DoTask','-full')` と `disp(hT)` で API/property を introspect。前提＝D3.2 は WG 予約ゆえ **WG 'TrigLegato130-2' を Resource Config で Remove** して解放。`allowRetrigger=0` 既定で D2.2 最初の1発のみ。
  - 波形: 出力 buffer に **N×cycle の遅延位置へ単発パルス**。実測 `R=100 kHz・nSamp=420000（4.2 s）・~4.000 s 遅延（N=500×8 ms）・150 ms パルス`。
  - 位置決め: `N`（target cycle）で着弾 cycle を指定。**`N=500 → 着弾 cycle #501`（+1 一定オフセット・counting 規約）→ 狙うなら `N=目標cycle−1`**。
  - **検証 PASS（2026-06-18）**: `run-01_00002`/`00003`/`00004`（4-line・8 ms cycle・1000 cyc・N=500）で head_pad 2.2286/1.9838/1.1554 s（~1.07 s≈134 cyc ばらつき）にもかかわらず **着弾 cycle 全て #501**＝決定論成立。150 ms 単発 5.08 V・`diag_ttl` clean。
  - clock 一致（cosmetic）: head_pad が大きい run で recorder 窓が scan 末尾の数 cyc を切り 994–996/1000 [CHECK]・短い run（00004）は 1000/1000 [OK]＝**コマ落ちでなく recorder 末尾切れ**・injection に無関係。
- 物理到達遅延は別途キャリブの定数オフセット（`physical_delay_offset_s`・t0 に折り込まない）。
- **次段（GUI）＝v1 完了（2026-06-18）**: `N`/pulse/enable を入れて arm/disarm する**薄い GUI**（config 前面・ロジックは UF 側・§2.2／`syncControlPanel`）。`N=目標cycle−1` を表示で吸収。cycle period は **hSI 自動取得（`hRoiManager.scanFramePeriod`・`alsCyclePeriodS`）で done（2026-06-19）**。

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
- **R1（契約 emission・gate 条件2 emission 部）closed（2026-06-19）**: `make_trigger_sync.py` を **trigger_sync 単一正本 emitter** に確定（`SCHEMA_VERSION=0.2.0`／ALS の `als_datafile_timing` を branch-A clock から schema 準拠で構築／境界 `<=`＝als_inject_align の cycle 規約と数式等価＝`searchsorted(edges,idx,'right')`）。`als_inject_align.py --emit-sidecar` は make_trigger_sync へ **完全委譲**（出力 byte 一致を `Compare-Object` で確認・旧 `als_datafile_timing_block` 削除）。gate② 採用 3 run（`run-01_00002`/`00003`/`00004`）で sidecar v0.2.0 VALID・inject_cycle 全て #501。旧 emit は `als_clock_loopback`/`residual_offset_s`/`inject_cycle_1based` の v0.1.0 形で 10 errors INVALID だった＝R1 が不可逆取得前に捕捉。schema は `schema_version` を `const "0.2.0"` に pin（stale emitter は loud に INVALID）。
- **Layer-2 .h5 QC ダッシュボード第一弾 done（2026-06-19）**: `qc_core.py`（UI 非依存・1 dict で injector 診断／inject→cycle・frame／head_pad／behavior 要約／ALS sweep／cycle-count cross-check・規約は make_trigger_sync と一致＝`<=`/median rate）＋ `qc_dashboard.py`（PyQtGraph・ファイル選択 1 つで `diag_ttl`→`als_inject_align`→`sweep_quality` を畳む・`.meta.txt` 有無で ALS/galvo 自動判定・mode-general）。実機 run-01_00004 で contract 値（inject_cycle #501・head_pad 1.155・sweep PASS）完全再現。次＝⑤ ALS×raster overlay（napari）。
  - **新所見①**: `.scnnr.dat` が pmt/frame_clock/commanded より **12 cycle 短い（988 vs 1000）**＝feedback stream の tail-clip 疑い → `feedback_on_pmt_grid` は scnnr cycle 数で出るので **pmt(1000)↔feedback(988) の per-cycle 対応が末尾でズレ得る**。overlay 時に先頭/末尾どちらが欠けるか要確認。QC で cross-check 可視化済。
  - **新所見②〔切り分け済・2026-06-20〕**: behavior ノイズの head_pad 一致は当初 scanner EMI 疑いだったが、`emi_quant.py`〔idle/scan 窓 RMS＋PSD・`--compare` で scanner-off baseline〕で定量 → **EMI step 1.42x・主ピーク 50/150Hz〔125Hz cycle 高調波でない〕・baseline≈idle≈0.016**＝**50Hz 電源 mains 主体**、scanner EMI は副次。treadmill は Sawtelle teensy の **decoded speed/dir**（無動物＝ベルト不動ゆえ両 ch が mains 床のみ＝瓜二つ）。in-vivo 前のアクション＝**接地対策**（シールド/差動/スター GND）。`emi_quant.py` は取得側 `src/python`。
- **解析の time-0（設計メモ・2026-06-19）**: 撮像アンカー＝cycle 1（注入は決定論で #501＝撮像開始 4.0s 後・run 間一致）／ダイナミクスアンカー＝注入 TTL エッジ（cycle 1–500 が baseline・cycle 501 から post）。両軸は定数 501 cycle≈4.0s で変換可＝cross-run 重ね合わせが補正なしで揃う（決定論注入の実利）。トレーサ到達は `physical_delay_offset_s`（定数）を下流加算。
- 解析側ログ詳細: `handoff_summary_20260609.md`。

## 改訂履歴

| 日付 | 変更 |
|---|---|
| 2026-06-20 | **in-vivo 準備: C2 behavior 契約 closed＋C4 EMI=mains 訂正＋C1 pixel-size 摘発（pending）＋GUI v2**（取得側・正本＝status/handoff_20260620）。**C2**: trigger_sync schema **0.2.0→0.3.0**（top-level `recorded_channels`〔全 dataset の name/ai/role/units/range_v〕＋`n_samples`・`schema_version` const 更新）、`make_trigger_sync` が `ROLE_MAP` で emit〔未マップ ch は raise〕・`als_datafile` basename 化、実 ALS `run-02_00005` で **VALID・inject_cycle #501・1000/1000・head_pad 2.348+500cyc/125Hz=4.0s→t0 6.348s**。`behavior_sidecar`(method-B) deprecate → **behavior を契約に closed**。**C4**: `emi_quant.py`〔idle/scan 窓 AC-RMS＋PSD〕で **EMI step 1.42x・主ピーク 50/150Hz〔125Hz cycle 高調波でない・`*`無し〕・baseline≈idle≈0.016** → behavior ノイズ＝**50Hz 電源 mains 主体**、scanner EMI は副次＝**新所見②〔scanner EMI 疑い〕を訂正**・対策優先＝接地。**C1**: `dump_si_metadata.py` で実機 raster 検証 → **`objectiveResolution=15`〔SI default 未校正〕**＝FOV 202µm 誤報、真 465µm→真値 **0.908µm/px**〔figure の 1.1px/µm が正〕。直し＝MDF `objectiveResolution≈34.4`＋SI 完全再起動だが**今回反映されず 15 のまま＝pending（次の実機）**。C1 PASS まで figure は `--px-per-um 1.1` 維持。treadmill＝Sawtelle teensy の **decoded speed/dir**〔生 A/B でない・0–3.3V・100mm/s=2.5V〕、無動物ゆえ speed≈dir。**GUI v2**（cycle# 直接入力〔N=target−1〕・STALE 検出＋Apply&Arm・Test fire・cycle period auto-track〔scanFramePeriod〕）＝「500→5 効かない」〔off-by-one＋armed ラッチ〕修正。in-vivo 移行 runsheet 作成（取得側）。コード配置決定（figure→解析 repo）。**残＝C1 実機（objectiveResolution 校正＋SI metadata SOP）**。 |
| 2026-06-19 | **R1（契約 emission・gate 条件2 emission 部）PASS ＋ cycle_period 自動化 ＋ emitter 一本化**（実機＋オフライン）。R1: gate② 採用 3 run（`run-01_00002`/`00003`/`00004`）で `make_trigger_sync.py` が trigger_sync sidecar を **v0.2.0 VALID** 出力・**inject_cycle 全て #501**（head_pad 1.155/2.229/1.984 s ばらつき下で不変＝契約側でも決定論再現）。emitter を **make_trigger_sync に単一正本化**（`SCHEMA_VERSION` 0.1.0→0.2.0・ALS `als_datafile_timing` を branch-A clock〔=h5 frame_clock dataset〕から schema 準拠で構築・境界 `<=`＝`searchsorted 'right'`）、`als_inject_align.py --emit-sidecar` は委譲化（旧 `als_datafile_timing_block` 削除・`Compare-Object` 無出力＝byte 一致）。**発見**: 旧 emit は `als_clock_loopback`/`residual_offset_s`/`inject_cycle_1based` 等の v0.1.0 形で schema INVALID（10 errors）＝R1 が不可逆取得前にドリフト捕捉。schema `schema_version` を `const "0.2.0"` に pin（stale emitter は loud に INVALID）。cycle_period: `als_cycle_probe.m` で live hSI を introspect→`hRoiManager.scanFramePeriod`(=0.008 s)確定→単一正本 helper `alsCyclePeriodS.m` を `syncArmStart`/`syncControlPanel` が読む版に（ハードコード 8ms 廃止・override drift は arm 時 warn）。→ **gate 条件2 の契約 emission 部 closed**。残 Tier-0＝SI 自動 metadata の実機 SOP 検証・behavior/injector を契約に。 |
| 2026-06-18 | **本番前ハードウェアゲート② PASS＝injector を DoTask v4 で deterministic fixed-cycle 化（WG 廃止）**（実機）。WG 'Trig Legato130' は ALS 下で arm 不安定（`startTask`→`linePeriod` が `StimulusField` で assert・ErrorHandler が握り潰し `[sync] armed` が false positive）→ **D3.2 上に raw `dabs.vidrio.ddi.rdi.DoTask`（finite・trig `/vDAQ0/D2.2`/rising）を直接立て**、`linePeriod` を呼ばず ALS 下で素直に start。`syncArmStart` が **acqModeStart で auto-arm**（`filterByName('vDAQ0')`→`createDoTask`/`addChannel(…,0)`/`convertToBufferedTask`/`sampleRate`(property)/`sampleMode='finite'`/`samplesPerTrigger`/`writeOutputBuffer`/`cfgDigEdgeStartTrig('/vDAQ0/D2.2')`/`start`・**`cfgSampClkTiming` は 'not done' で不可→property 代替・`sampleMode` 既定 continuous→finite 必須・Vidrio は `.p`（methods -full/disp で introspect）**・実測 `R=100kHz・nSamp=420000・~4.000s 遅延・150ms パルス`・widget 手動 Start 不要に）。**検証 PASS**: `run-01_00002`/`00003`/`00004`（4-line・8ms cycle・1000cyc・N=500）で head_pad 2.2286/1.9838/1.1554s（~1.07s≈134cyc ばらつき）にもかかわらず **着弾 cycle 全て #501**＝決定論成立。150ms 単発 5.08V・`diag_ttl` clean。`N=目標cycle−1`（+1 オフセット）。clock 一致 994–1000/1000 は **recorder 末尾切れ**（短 head_pad の 00004 は 1000/1000 [OK]・コマ落ちでない・cosmetic）。→ **本番前ゲート①②とも完了**。次段＝injection GUI **v1 完了**（`syncControlPanel`・薄い config 前面）＋残り Tier-0（契約・metadata 実機検証・behavior/injector を契約に）・cycle_period の hSI 自動取得（現状ハードコード 8ms）。 |
| 2026-06-12 | **本番前ゲート①（1-min scan stop）closed＋②（fixed-frame injection）機構特定（検証残）**（実機）。①: 原因＝有限 `hSI.hStackManager.framesPerSlice`（ALS=cycle 数。総 grab frame=framesPerSlice×numSlices×numVolumes・旧「10000/10000 edges」も 166.67Hz×60s の programmed 完走で fault ではない）→ 実 4-line config で数分連続完走＋`Inf` 持続を確認＝**closed**。post-hoc QC `run-02_00001`（4-line/400s）: diag_ttl ✓／als_inject_align ✓（49999/50000・residual 2.2426s・inject cycle#487）／sweep_quality ✓ PASS（50000cyc・pp~9.5 一定）。②: ScanImage WG 'Trig Legato130'(D3.2) を **frame clock で hardware-trigger** する機構を特定（host timer を排す）。`D0.0`(frame clock out・vDAQgalvo 所有＝WG 予約不可) を**物理 T 分岐で `D2.2` へ** → WG Start Trigger=`/vDAQ0/D2.2`(rising)。**鍵＝WG task は grab 前に widget で Start(arm) が必要**（Apply のみでは無出力）。widget Start→grab で AI7 に clean 単発を記録（`run-06_00005`/`00007`・edges@2.5V=1）。continuous は永続 on で one-shot 不適 → finite 化が必要。**検証残（次回）**: als_inject_align で複数 run の着弾 cycle 一致 → finite 単発化 → 短パルス → `Start=N×cycle` → 複数 run 一致で gate② PASS → `syncArmStart` を acqModeStart-arm 版へ。配線 `vdaq_io_map.yaml` に D0.0→D2.2 追加。WG widget の SceneTree replaceChild storm は GUI ノイズ（出力に無関係）。 |
| 2026-06-09 | **方式A ALS go を multi-line（3-line）へ拡張**（run-01_00005）。cycle 6.0ms/166.67Hz・5000cyc×3line=30s。①overflow無 ②injector 単発5V 208.8ms clean・競合無 ③branch A clock [OK] 5000/5000・residual 2.1974s。injector cycle#655 着弾（ROI5 pause＝無害）。pause-before-each-line で line skip 無し。**掃引品質 PASS**（新ツール `sweep_quality.py`: per-cycle pp median 4.92・5th 4.904・全cyc安定＝park病なし）。次フェーズ戦略反映: 最優先＝①1-min stop 原因探索＋改善 ②決まったフレーム投与（clock/frame-trigger 化）→通れば実験移行。並行＝behavior 記録解析・FastZ 導入・解析一本化・injection/behavior GUI。4-line はできる見込みで skip、より速い ALS は次回最適化案。 |
| 2026-06-08 | **方式A ALS go（single-line）**。branch A clock 成立（配線変更ゼロ）。residual 3.1–3.5s 可変＝毎 grab 測定。injector AI7 path 修正（単発5V）・`delaySec>head_pad`（=6）で cycle 着弾。新ツール `als_inject_align.py`・`diag_ttl.py`。P2 2-line exact＝Track-W B loader closed。resonant 据え置き→finalize 2 mode 化。`logFramesPerFile=Inf`（per-scanner）。4-line は ROI GUI バグで未完。 |
| 2026-06-06 | 解析側 P2（single-line exact）・trigger_sync emitter（galvo `.h5` で schema VALID）。jsonschema を ivwib へ。 |
| 2026-06-05 (b) | P1: galvo go 数値確定。決定: recorder-start≠frame-0／frame_clock anchor／median rate。trigger_sync schema draft 化。 |
| 2026-06-05 (a) | 方式A e2e **galvo go**。Data Recorder 配線・run-config・UF 登録・HDF5 レイアウト確定・受け入れ ①②③。 |
