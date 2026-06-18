# ScanImage / vDAQ 内部仕様・API・地雷リファレンス

```
purpose:  ScanImage Premium 2026 ＋ Vidrio/MBF vDAQ の、ドキュメントに無い/分かりにくい
          内部仕様・API シグネチャ・落とし穴を一箇所に集約。実機で確定した事実のみ。
scope:    microscope_control_dev（取得側）。MATLAB R2025b・vDAQ(Kintex UltraScale, PCIe)。
last_updated: 2026-06-18
related:  status.md / sync_architecture.md / vdaq_io_map.yaml / trigger_sync.schema.json
          / src/matlab/{syncArmStart,syncDisarm,syncControlPanel}.m
凡例:     [確] = 実機で確認 / [文] = 公式図/doc 由来 / [注] = 落とし穴
```

---

## 1. vDAQ ハードウェア & リソース

### 1.1 ブレイクアウトと向き制約 [文][確]
- AI×12（AI0–11）／AO×12（AO0–11）／DIO 4 群 D0–D3 ×8 = 32 線／+5V／knob。
- **DIO 向き制約（IMG_9982・重要）**: `D0=In/Out`・`D1=In/Out`・`D2=Inputs Only`・`D3=Outputs Only`。
  - → 出力は D0/D1/D3、入力は D0/D1/D2。**D2.x は出力にできない**（WG で D2.0 が選べなかった原因）。
- 高速 AI（PMT2100×3＋自作 PD）は**前面 SMB（4ch 125 MS/s）**。ブレイクアウトの AIx ではない。

### 1.2 単一クロックドメイン [確]
- imaging・Data Recorder・Aux が**同一 vDAQ master clock**。
- これが「behavior を 1–5 kHz で imaging と同居できる」根拠（別 session 不要・MEX 競合なし）。

### 1.3 リソースアクセス（MATLAB） [確]
```matlab
rs   = dabs.resources.ResourceStore();
hDAQ = rs.filterByName('vDAQ0');   % → vDAQR1 (class dabs.resources.daqs.vDAQR1)
wgs  = rs.filterByClass('dabs.generic.WaveformGenerator');
```
- `hDAQ` は `hDOs[1×8]` / `hDIs[1×8]` / `hDIOs[1×16]` を持つ。
- DO control（例 D3.2）: `/vDAQ0/D3.2`・channelID・`maxSampleRate=20 MHz`・`supportsHardwareTiming=1`・`reserverInfo`（予約者表示）。

### 1.4 確定 I/O マップ（自構成） [確]
| port | 用途 |
|---|---|
| D0.0 (out) | frame clock out（vDAQgalvo 所有・**trigger 入力に予約不可**） |
| D2.2 (in)  | frame clock の T 分岐（trigger 入力・D2=Inputs Only ゆえ ownable） |
| D3.2 (out) | injector TTL（v4 DoTask が駆動・→T→ AI7＋Legato＋D2.1 aux） |
| AI6 (in)   | frame clock ループバック（Data Recorder `frame_clock`） |
| AI7 (in)   | injector TTL（Data Recorder `Legato130_TTL`＝**t0 正本**） |
| AI4 / AI5  | behavior（treadmill_dir / treadmill_speed） |
| D2.0/D3.0  | resonant sync / enable ／ D3.1 = shutter(KSC101) |

> **配線の肝**: D0.0 は所有ロックで trigger 入力に直接予約できない → **物理 T 分岐で D2.2（入力専用・ownable）へ**渡す。出力→入力なので T 分岐は安全。

---

## 2. DoTask API（`dabs.vidrio.ddi.rdi.DoTask`） — v4 注入の中核 [確]

WaveformGenerator をバイパスして DO を直接叩く低レベル task。**ALS 下でも素直に start する**（`linePeriod` を呼ばない）。

### 2.1 落とし穴 3 点 [注]
1. **`cfgSampClkTiming(rate)` は `not done` で落ちる** → 使わず **`sampleRate` property を直接代入**。
2. **`sampleMode` 既定が `'continuous'`** → 単発にするには **`'finite'` を明示**（さもなくば buffer がループ）。
3. **クラスは `.p`（P-code・ソース読めない）** → `methods('dabs.vidrio.ddi.rdi.DoTask','-full')` と `disp(hT)` / `properties(hT)` で introspect。
   - 追加: **D3.2 は WG が予約**する → WG を Resource Config で Remove してから DoTask を立てる。

### 2.2 確定シーケンス（finite 単発・hardware-trigger）
```matlab
hDAQ = dabs.resources.ResourceStore().filterByName('vDAQ0');     % vDAQR1
hT = dabs.vidrio.ddi.rdi.DoTask.createDoTask(hDAQ,'injTrig');    % static factory
hT.addChannel('D3.2','injTrig',0);     % (channel, name, initialValue) init 0 = idle LOW
hT.convertToBufferedTask();            % on-demand → buffered（必須）
hT.sampleRate = R_Hz;                  % property（cfgSampClkTiming の代替）
hT.sampleMode = 'finite';              % 既定 continuous を上書き
hT.samplesPerTrigger = nSamp;          % trigger 1発で出す sample 数
hT.writeOutputBuffer(pulseVec);        % nSamp = numel(pulseVec)
hT.cfgDigEdgeStartTrig('/vDAQ0/D2.2'); % 1引数。edge は startTriggerEdge 既定 rising
hT.start();                            % arm。allowRetrigger=0 で最初の1エッジのみ
% 後始末: hT.stop()/abort()→ hT.setChannelOutputValues(0)（line LOW）→ delete(hT)
```
- **着弾位置**: buffer 前方 zero 長 `= N × cycle_period × R_Hz` で「N cycle 後に撃つ」を表現。
- **buffer 長 = sample 数**（`nSamp` は writeOutputBuffer のベクトル長で決まる）。
- timebase: 内部クロック（`sampleClockTimebaseSource='200MHzTimebase'`）。

### 2.3 メソッド（`methods -full` 抜粋）
- static: `createDoTask(device,name)`（/ createAi/Ao/DiTask）
- `addChannel(channel,channelName,initialValue)` / `addChannels(chans,names)`
- `convertToBufferedTask()`
- `cfgDigEdgeStartTrig(v)`（端子のみ・edge は property）/ `disableStartTrig` / `softTrigger`
- `writeOutputBuffer(data)` / `writeOutputBufferAsync(data,cb)`
- `start` / `stop` / `abort` / `waitUntilTaskDone(timeout)`
- `setChannelOutputValues(data)` / `tristateOutputs` / `reserveResource` / `unreserveResource`
- `verifyBuffers` / `verifyConfig`

### 2.4 主要プロパティ（`disp(hT)` 既定値）
| property | 既定 | 備考 |
|---|---|---|
| `sampleMode` | `continuous` | **finite に上書き必須** |
| `startTriggerEdge` | `rising` | cfgDigEdgeStartTrig は端子だけ渡せば可 |
| `allowRetrigger` | `0` | 最初の trigger エッジ1発のみ |
| `sampleRate` | `1e6` | 直接書ける（cfgSampClkTiming 代替） |
| `maxSampleRate` | `2e7` | 20 MHz |
| `startTrigger` | `''` | property 直叩きでも設定可 |
| `samplesPerTrigger` | `0` | finite で設定 |
| `direction`/`type` | `out`/`digital` | |
| `bufferSize` | `0` | writeOutputBuffer で確定 |
| `sampleClockTimebaseRate` | `2e8` | 200 MHz |

---

## 3. WaveformGenerator（`dabs.generic.WaveformGenerator`） — ALS で却下 [確][注]

> **結論: generic WG は ALS scan mode で arm できない。injector には DoTask（§2）を使う。**

- `startTask` が毎回 `updateWaveform → computeWaveform → refreshWvfmParams → hSI.hScan2D.scannerset.linePeriod(ss)` で波形を再計算。
- `GalvoGalvo.linePeriod`（行 489）が `assert(isa(scanfield,'ImagingField'))` を持つ → **ALS の `StimulusField` で必ず落ちる**。
- **pre-compute は無意味**（startTask が作り直す）／**Show Widget OFF も無効**（widget 再描画でなく startTask 内部の再計算が原因）。
- **`[sync] armed` が false positive になり得る**: SI の ErrorHandler が内部例外を握り潰し try/catch に伝播しない → 「正常終了」に見えて実は task 未起動（AI7 flat）。**ログでなく実出力で検証すること**。
- WG は DO 線を**永続予約**（`reserverInfo: <Reserved: TrigLegato130-2>`）→ DoTask に明け渡すには Resource Config で WG を **Remove**。
- WG は widget で Start(arm) しないと出力しない（Apply だけでは task 未起動）— ただし ALS ではこの経路自体が死んでいる。

---

## 4. ScanImage scan mode & ALS 仕様 [確][文]

- `SI.hScan2D.scanMode`: `'linear'`（galvo-galvo）/ `'resonant'`。
- **ALS（Arbitrary Line Scanning）は galvo-galvo 専用**。`StimulusField` / `scanimage.mroi.stimulusfunctions.*`（例 line）を使う。resonant は固定正弦波ゆえ ALS 不可。
- **ALS の「frame」= cycle**。`D0.0→AI6` frame-clock ループバックが **cycle ごとに 1 エッジ**（"branch-A clock"）。
- **`framesPerSlice`（ALS=cycle 数）**: 総 grab frame = `framesPerSlice × numSlices × numVolumes`。**有限値だと programmed 完走で「停止」に見える**（fault ではない）→ **持続取得は `Inf`**。
- **ALS は TIFF を出さない**（resonant/raster は出す）。ALS データ = stem 共通 3 ファイル: `.meta.txt` / `.pmt.dat` / `.scnnr.dat`。
- **on-disk PMT は raw int16 counts（pre-offset）**: 忠実な既定は `subtract_offset=False`。
- **ALS feedback upsampling**: `×(sampleRate/sampleRateFdbk)`（非整数）→ 補間（block-repeat 不可）。
- **mROI**: raster mROI は galvo/resonant とも可。**ALS 流の arbitrary-line mROI は galvo-galvo 専用**。
- **`Optimize Waveform` は vendor バグ（MBF 25850・undefined `feedbackPoints`）** → 運用は **Reset Waveform → Calibrate + Test**。galvo feedback calibration は SI 起動毎に自動。
- **ALS ROI GUI "Add ROI" バグ**（`ArbitraryLineScanRoiGui>addRoi` 行 77 → `most.gui.style(uibutton ... 'Add ROI')`）: 4-line で発生・3-line で未発生。回避＝SI 再起動／保存 ROI ロード／2-line 複製／programmatic builder。
- ファイル命名: 空 0KB `_00002` は `hScan2D.logFramesPerFile=Inf`（**per-scanner**）で抑止。`_00001` カウンタは SI 仕様で消せない（stem 扱い）。

---

## 5. Resonant scanning（将来移行・参考） [確(物理)]

- fast 軸 = 固定周波数の正弦波、slow 軸 = galvo。**line rate は resonant 周波数で固定**（unidir = f_res・bidir = 2×f_res）。**frame rate = line_rate ÷ numLines**。
- **X を絞っても rate は上がらない**（line period 固定）。速くするのは「Y line 数を減らす」「mROI で死領域を削る」。
- 単一 line = Y park ＋ resonant X（full amplitude・kHz）。任意角は scan rotation＋park で可。任意 multi/曲線は不可。
- **正弦波速度＝dwell 不均一** → SRS の SNR に効く。sinusoid resampling が要る。
- 100 Hz は小 ROI で容易（8–12kHz resonant → 16–24k lines/s → 100Hz は ~160–240 行）。
- **注入同期はそのまま乗る**: resonant でも frame clock は出る → `frame_clock` anchor（trigger_sync schema の else 分岐）。N は「target cycle」→「target frame」（delay=N/frame_rate）。QC は `als_inject_align`（ALS 専用）でなく frame_clock 分岐。

---

## 6. Data Recorder（ScanImage-native・vDAQ） [確]

- **SI ネイティブ**（別 session/MEX 不要）。外部 NI ボードを別 session で vDAQ に握ると SI と排他衝突（過去の DO 不動の原因）。
- run-config: **Auto Start ON**（=共通 acq-start）／Use Trigger OFF／**Sample Rate 5000 Hz**（実下限 ~3052 Hz＝FPGA 分周由来・doc の 500 ではない・上限 500 kHz）／Duration Inf／`logFramesPerFile=Inf`。
- **HDF5 レイアウト**: root `/` attr `samplerate`（全 ch 共通）／dataset 名 = Recorded Name／float32・MaxSize Inf・ChunkSize／attr `units`/`conversionMultiplier`／**time vector 無し → t = index / samplerate**。
- **Auto-Start head_pad**: **recorder-start ≠ frame/cycle-0**。head_pad は**非ゼロかつ run ごとに可変**（galvo ~1.975s・ALS ~1.15–3.5s）。→ 注入は frame/cycle アンカー（recorder-start ではない）。

---

## 7. 同期・トリガ原則（確定） [確]

- **vDAQ = master/hub**: 全信号が単一 FPGA クロック領域。
- **frame clock 配線**: D0.0 out（所有ロック）→ 物理 T 分岐 → AI6（記録）＋ D2.2（trigger 入力）。
- **注入 t0 正本 = Data Recorder の AI7 TTL エッジ**（scan-mode 非依存）。TIFF Aux-Trigger は不可（resonant 限定・ALS は TIFF 無）。
- **決定論 = hardware frame-clock trigger**（host timer ではない）: head_pad が ~1秒以上ばらついても着弾 cycle は不動（gate②: 3 run #501・head_pad 1.16–2.23s）。
- **per-frame host UF 禁止**（imaging rate で frame queue overflow）。trigger ロジックは **acqModeStart 1 回＋hardware-clocked**。
- 33 Hz 付近の "overflow" 上限は display/保存側（同期 UF は per-frame 負荷ゼロ）。
- inject_cycle は `(t0 − head_pad)/cycle_period`（**time-anchor**）で算出 → branch-A clock の数本取りこぼし（[CHECK]）に robust。

---

## 8. MATLAB / ScanImage 環境の地雷 [確][注]

- **SI 起動中に `clear functions` / `clear all` 厳禁** — MDF/resource singleton を unload（"MDF unloaded"・WG 消失）。復旧＝SI 再起動。**flush は `clear <関数名>` のみ**。
- **User Function は Delete→再追加で fresh handle**（Enable トグルだけだと旧参照を掴むことがある）。
- 注入 UF 登録: `acqModeStart→syncArmStart` / `acqAbort`・`acqDone→syncDisarm` / **`frameAcquired` 空**。
- **P-code クラスの introspect**: `methods('pkg.Class','-full')`（シグネチャ）・`disp(obj)`（property＋値）・`properties(obj)`。`which pkg.Class` は `.p` のパスを返すだけ（中身は読めない）。
- conda env: `mcd-quicklook`。`python` 直叩き（env アクティブ時）or `$py` フルパス。

---

## 9. クイックリファレンス（チートシート）

```matlab
% --- リソース取得 ---
hDAQ = dabs.resources.ResourceStore().filterByName('vDAQ0');

% --- DoTask 単発 finite（hardware-trigger）---
hT = dabs.vidrio.ddi.rdi.DoTask.createDoTask(hDAQ,'injTrig');
hT.addChannel('D3.2','injTrig',0);
hT.convertToBufferedTask();
hT.sampleRate = 1e5;            % cfgSampClkTiming は使わない（'not done'）
hT.sampleMode = 'finite';      % 既定 continuous を上書き
hT.samplesPerTrigger = numel(buf);
hT.writeOutputBuffer(buf);     % buf = [zeros(N*cyc*R); ones(pw*R); zeros(tail)]
hT.cfgDigEdgeStartTrig('/vDAQ0/D2.2');   % edge=rising 既定
hT.start();

% --- introspect（.p クラス）---
methods('dabs.vidrio.ddi.rdi.DoTask','-full')
disp(hT)

% --- 禁止 ---
% clear functions / clear all   ← SI 起動中は厳禁
```

| やりたいこと | 正解 | 落とし穴 |
|---|---|---|
| DO sample rate 設定 | `hT.sampleRate = R` | `cfgSampClkTiming` は `not done` |
| 単発（ループさせない） | `hT.sampleMode='finite'` | 既定は continuous |
| buffered 出力 | `convertToBufferedTask()` 先に | on-demand のままだと不可 |
| ALS 中に injector trigger | DoTask（§2） | WG は ALS で arm 不可 |
| D3.2 を DoTask で使う | WG を Resource Config で Remove | WG が永続予約 |
| 注入を frame に揃える | frame-clock trigger（D2.2） | host timer は head_pad で毎回ズレる |
| 持続 ALS 取得 | `framesPerSlice=Inf` | 有限値は programmed 完走で「停止」 |
| 関数を flush | `clear <関数名>` | `clear all`/`clear functions` は MDF unload |
```
