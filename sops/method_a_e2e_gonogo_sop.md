# SOP — 方式A end-to-end go/no-go（injector TTL × Data Recorder × 整列）2026-06-05

```
last_updated:   2026-06-05
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（優先順位の単一の正）
design_truth:   microscope_control_dev/docs/sync_architecture.md（同期設計の正本・t0=Data Recorder TTL）
scope:          §3.5＋Phase 1 を 1 本で実機検証する手順。go/no-go の単一テスト録り。
                ① acqModeStart 単発発火＋overflow 無し / ② injector TTL が Data Recorder HDF5 に載る /
                ③ imaging・ALS と共通 acq-start で整列。ここを潰すと t0 機構が確定する。
related:        status.md §2/§3/§3.5, vdaq_io_map.yaml, syncArmStart.m / syncDisarm.m,
                legatoInjectStart.m（旧・単体版）, syncControlPanel.m
ref:            ScanImage Data Recorder 仕様 https://docs.scanimage.org/Basic+Features/Data+Recorder.html
```

> このテストの出口＝**実 HDF5 レイアウト確定 → 解析側 `trigger_sync` schema 解禁**。
> ここが Track-M（frame 高速化 vs line-scan）と解析側 schema を gate する Tier0。

---

## 0. go/no-go（このテストで確定すること）

| # | 確認項目 | PASS 条件 | これが意味すること |
|---|---|---|---|
| ① | acqModeStart 単発発火＋overflow 無し | ≤33 Hz の grab で console に `[sync] injector ON/OFF`、かつ **`Frame queue overflow` が出ない**（全 mode） | per-frame ソフトを同期経路に置かない設計が実機で成立 |
| ② | injector TTL が Data Recorder HDF5 に載る | 出力 `.h5` の `injector_ttl` dataset に 0→1→0 のパルスが見える | t0 を同一 vDAQ クロック・同 HDF5 に録れる（scan モード非依存） |
| ③ | imaging/ALS と共通 acq-start で整列 | Auto Start で grab と同時に録り出す＋（推奨）同 HDF5 内 `frame_clock` と injector edge が同一 timebase に乗る | 注入 t0 を imaging/ALS と offline 整列できる |

**メタ目標**: ①②③ が **galvo / ALS / resonant の 3 mode で並走**して成立すれば、t0 機構（= Data Recorder TTL edge・全 mode 共通）が確定し、roadmap §3 の契約を「HDF5 behavior＋injector-TTL」で固められる。

---

## 1. 前提・配線（事前チェック）

- **WG 生成**: `Trig Legato130` が `D3.2`(WG TTL) に出る（`writeLineToVal` 確認済）。`vdaq_io_map.yaml` の D3.2/D2.1 は confirmed。
- **T 分岐**（injector の物理線・sync_architecture §3）:
  - ① `D3.2` → **空き AI（例 `AI7`）= Data Recorder で TTL 記録（t0 正本・全 mode）** ← ② の主役。
  - ② `D2.1`(Aux) → resonant 時の**任意クロスチェック**のみ（galvo/ALS では真値に使わない）。
  - ③ Legato 本体。
- **（推奨）整列クロスチェック線**: imaging **Frame Clock Out → 別の空き AI（例 `AI6`）**。同 Data Recorder に `frame_clock` として録る。
  これで Auto-Start の start 遅延に依存せず、HDF5 内部で injector edge を frame 列に写像できる。**ALS は frame が無い**ため non-applicable → common acq-start ＋ ALS data file の timing で代替（§4③）。
- **AI レンジ**: WG は 0/5 V TTL。vDAQ low-speed AI レンジ内（±10 V 想定）なので直結で可。レンジ超過なら attenuate/level-shift。
- **Data Recorder device** を Resource Configuration Window に追加済みにする。

---

## 2. 設定

### 2.1 trigger 設定（`syncControlPanel` → Apply to base）
base `syncTriggers`（struct array）:
```matlab
syncTriggers = struct('name','injector','wg','Trig Legato130', ...
                      'delaySec',2,'pulseSec',0.2,'enabled',true);
% delaySec の代わりに targetFrame でも可（delaySec = targetFrame / scanFrameRate）。
```
> `syncControlPanel` の表に injector 行を入れて "Apply to base" でも同じ。

### 2.2 User Function 登録（ScanImage IO タブ / `hSI.hUserFunctions`）
| event | function |
|---|---|
| `acqModeStart` | `syncArmStart`（1 回だけ arm。**legato 単体なら `legatoInjectStart`**） |
| `acqAbort` / `acqDone` | `syncDisarm`（タイマ掃除＋全 WG 線 LOW。**legato 単体なら `legatoInjectStop`**） |

**要確認: `frameAcquired` には何も登録しない**（= overflow 回避の要・sync_architecture §4-1）。

### 2.3 Data Recorder 設定（Resource config → Data Recorder widget）
- **Add Signal** → injector AI（例 `AI7`）: Signal Name `injector_ttl` / Units `V` / Multiplier `1`。
- **（推奨）Add Signal** → frame clock AI（例 `AI6`）: Name `frame_clock`。
- **（任意）** behavior AI（`AI4`+）も足すと Phase 1 を同録りできる（`velocity` 等）。
- **Sample Rate**: まず `1000` Hz（behavior と整合）。edge 分解能 = 1/fs（1 kHz なら ±1 ms）。必要なら up to 500 kHz。
- **Sample Duration**: `Inf`（grab stop まで録る）。
- **Auto Start**: **ON** ← これが「共通 acq-start」。grab で start/stop。
- **Use Trigger**: OFF（Auto Start で足りる。digital trigger は今回不要）。
- **Compression**: 長録りなら ON（GZip）。短いテストは任意。
- **File Basename / Directory**: imaging と同 stem（`raw/`）に落ちるよう設定。

---

## 3. 実行（mode 別・各回は短時間 grab）

順序＝**galvo（baseline）→ ALS → resonant**。各 mode で:

1. frame rate を **≤33 Hz** に（resonant は実効、ALS は line-scan 設定）。
2. **Grab 開始** → Data Recorder widget が自動で `Start`→`Stop` 表示に変わる（Auto Start 動作）。
3. `delaySec`（既定 2 s）後に injector が ON→OFF。console に `[sync] injector ON` / `OFF`。
4. **Grab 終了** → Data Recorder 停止 → `.h5` が出力される。
5. 記録: mode / frame rate / imaging file 名 / Data Recorder file 名。

> abort テストも 1 回: grab 中に Abort → `syncDisarm` が走り、injector 線が LOW に戻る（stuck-high 無し）ことを確認。

---

## 4. その場確認（go/no-go の 3 点）

- **①** MATLAB console と ScanImage に **`Frame queue overflow` が出ない**こと（全 mode・≤33 Hz）。
  出たら別 UF が `frameAcquired` に残っていないかを最初に疑う（syncArmStart は acqModeStart のみ）。
- **②** Data Recorder の **View** で `injector_ttl` にパルスが見える（または直後に §5 で h5read）。
- **③** `frame_clock` を録っていれば、同 `.h5` 内で injector edge と frame パルス列が**同一 timebase**に並ぶ（共通 start を待たず内部整列）。
  **ALS** は frame パルスが無いので、common acq-start（Auto Start）＋ ALS data file（`readLineScanDataFiles`）の timing で対応づけ。
  **resonant** のみ `D2.1` Aux → TIFF timestamp と t0 を任意クロスチェック。

---

## 5. オフライン検証（最小スクリプト）

```matlab
f  = 'raw\<basename>_00001.h5';
fs = h5readatt_or_known;               % 設定した Sample Rate [Hz]
ttl = h5read(f,'/injector_ttl');       % dataset 名は設定どおり
th  = 2.5;                              % 0/5V の中点
idx = find(ttl(1:end-1) < th & ttl(2:end) >= th, 1);  % 立ち上がり
t0  = (idx-1)/fs;                       % recorder start 基準の注入 t0 [s]
fprintf('injector t0 = %.4f s (sample %d)\n', t0, idx);

% --- frame_clock があれば frame 番号に写像（指定 targetFrame と一致するか） ---
% fc = h5read(f,'/frame_clock');
% fIdx = find(fc(1:end-1)<th & fc(2:end)>=th);   % 各 frame の立ち上がり
% frameAtInject = sum(fIdx <= idx);              % t0 直前までの frame 数
```

- `t0` は **trigger edge**。チューブ dead volume・ポンプ立上りは**別途キャリブする定数オフセット**（t0 に足し込まない）。
- behavior を同録りしていれば同 timebase で重ねて sanity check。

---

## 6. 判定と次手

**PASS（①②③ × 3 mode）** → 
- 実 HDF5 レイアウト確定: datasets = `injector_ttl`(=t0)・`frame_clock`・`behavior…`、attrs = sampleRate/units。
- これを持って**解析側 `trigger_sync` schema を確定**（roadmap §3 契約・取得側→解析側 coordinate・4 ファイル同期）。
- Track-M の gate（frame 高速化 vs line-scan）も判断材料が揃う。

**FAIL → fallback**
| 症状 | 切り分け |
|---|---|
| overflow が出る | `frameAcquired` に UF が残っていないか。syncArmStart は acqModeStart のみのはず |
| TTL が載らない | AI レンジ/配線/WG 出力（writeLineToVal 動作）/ Data Recorder の signal が正しい AI か |
| ALS・resonant で Data Recorder が並走しない/競合 | mode 別に切り分け。sample rate を下げて再試行。device 競合なら sync_architecture §4.5 で階層判断 |
| 整列がずれる | Auto-Start start 遅延に依存しない `frame_clock` 方式へ（本 SOP 推奨）。resonant は Aux と相互確認 |

---

## 7. メモ（既知の註）

- **コード註の陳腐化**: `legatoInjectStart.m` / `syncArmStart.m` のヘッダコメントは「real edge は `D2.1` Aux loopback が timestamp」と記載。2026-06-04 改訂で **t0 正本は Data Recorder TTL edge（全 mode）** に一本化済み。pulse 生成のコード動作は正しい（機能影響なし）→ **コメント 1 行の更新を推奨**。Aux は resonant 任意クロスチェックに格下げ。
- **t0 概念**: 注入の「タイミング」は任意（frame N / delaySec 指定）。「t0」は実際に立ったエッジの記録値＝解析の時間ゼロ。

---

## 改訂履歴

| 日付 | 変更 |
|---|---|
| 2026-06-05 | 初版。§3.5＋Phase 1 の単一 go/no-go テスト手順。Data Recorder 正本仕様（Auto Start=共通 acq-start・HDF5 dataset・500Hz–500kHz・timestamp ベクトル無し）を反映し、frame_clock 同録りを整列クロスチェックに採用。コード註陳腐化を記載。 |
