# Runsheet — 方式A e2e go/no-go（ALS 段）2026-06-05

```
last_updated:   2026-06-05
parent_sop:     microscope_control_dev/docs/method_a_e2e_gonogo_sop.md（正本。本稿は ALS 段の実行展開）
design_truth:   microscope_control_dev/docs/sync_architecture.md（§2 anchor／§4.5 device 階層）
priority_truth: in_vivo_water_imaging_brain/docs/strategy_roadmap.md（§4 Tier0／§5 gate／§4 Track-W B）
scope:          galvo 段 go（2026-06-05・数値確定済）を承けた ALS 段の単一ヘッドライン bench。
                SOP の generic 3-mode 手順から ALS 差分のみを 1 本に展開し、その場で埋める記録欄を付す。
                これは per-session runsheet（台帳でない）。決定は SOP/sync_architecture/roadmap に戻す。
related:        status.md §2/§3.5 / vdaq_io_map.yaml / trigger_sync.schema.json / datarecorder_loader.py
                / als_loader.py / als_sidecar.schema.json
```

> このランの出口 = **ALS で ①②③ PASS（下表）→ als_datafile_timing 整列が成立し、3 mode のうち 2 つ目が埋まる**。
> 続いて resonant 段。3 mode 揃いで `trigger_sync.schema.json` を finalize（version up・signals.behavior・$id 確定）。

---

## 0. このランの go/no-go（ALS 特化）

SOP §0 の 3 点を ALS に読み替えたもの。**③ が galvo と本質的に違う**（frame_clock が無い）。

| # | 確認項目 | PASS 条件（ALS） | 意味 |
|---|---|---|---|
| ① | acqModeStart 単発＋overflow 無し | ALS line-scan で console に `[sync] injector ON/OFF`、かつ `Frame queue overflow` が出ない | per-frame ソフトを同期経路に置かない設計が ALS でも成立 |
| ② | injector TTL が Data Recorder HDF5 に載る（**device 競合なし**） | 出力 `.h5` の `Legato130_TTL` に 0→1→0 が見える。ALS の高速 line-scan と Data Recorder（低速 AI）が同一 vDAQ で**並走して落ちない/破損しない** | t0 を ALS でも同一クロック・同 HDF5 に録れる（scan モード非依存の正本が ALS で実証） |
| ③ | **als_datafile_timing で整列できる** | common acq-start（Auto Start）で Data Recorder `.h5` と ALS データファイル（`readLineScanDataFiles`）が同一起点を共有し、recorder-relative な injector t0 を ALS データの cycle/sample へ写像できる。**residual offset（= ALS 版 head_pad）を数値で出す** | 注入 t0 を ALS imaging に offline 整列できる |

**メタ目標**: ①②③ が ALS で成立すれば t0 機構（Data Recorder TTL edge・全モード共通）が ALS でも確定。roadmap §5 gate 3 の ① に ALS が乗る。

---

## 1. galvo → ALS の差分（最初に読む・要点先出し）

galvo 段は済。ここだけ違う、を 5 点に圧縮。

1. **anchor = `als_datafile_timing`（frame_clock ではない）**。schema が強制（`scan_mode=als` → `anchor` const `als_datafile_timing`＋`als_datafile` 必須・`frame_timebase` は省く）。
2. **frame_clock のパルス列が無い**。D0.0→AI6 ループバックは ALS では非適用（ALS は per-frame clock を吐かない）。`datarecorder_loader.py` が **"frame_clock absent (expected for ALS)" / n_frames=0** を出すのが**正**（失敗ではない）。AI6 は ALS 段では load-bearing でない → 録っても flat。**Data Recorder の signal 構成は galvo と同一に保ち**（再設定ミス回避）、AI6 が flat=ALS 署名と割り切るのが楽。
3. **整列は common acq-start に依存**。ただし sync_architecture §2 が明言するとおり **common acq-start は近似**（recorder-start≠真の取得開始・offset あり）。galvo の head_pad（1.975 s）に相当する **ALS 版 offset を、このランで初めて数値化する**（= go/no-go ③ の核心）。
4. **注入タイミングは `delaySec` で指定**（`targetFrame` を使わない）。ALS の "frame rate" は line-scan の周回で曖昧なので、`delaySec`（recorder 起点・秒）が一義。
5. **ALS 取得の前提が増える**: Optimize Waveform はベンダーバグ（`feedbackPoints` undefined・MBF 25850）で不可 → **Reset Waveform で raw command AO に戻して acquisition**。`.scnnr.dat`（実スキャナ位置）が真値なので、後段 P2 用の als_ref 取りでは **Monitor Scanner Feedback ON**（§6）。

---

## 2. 前提・配線（ALS 特化チェック）

配線は galvo 段から**変更なし**（confirmed・`vdaq_io_map.yaml`）。下は ALS で再確認する点のみ。

- **injector chain（不変）**: WG `Trig Legato130` → `D3.2` → T 分岐 → ① `AI7`= Data Recorder `Legato130_TTL`（t0 正本・全モード）／② `D2.1` Aux（resonant 任意・ALS では不使用）／③ Legato 本体。
- **frame_clock（ALS では非適用）**: `D0.0`→`AI6` ループバックは ALS で**パルス無**。配線は残してよい（resonant 段で再使用）。Data Recorder の `frame_clock` signal は外しても残しても可（§1-2）。
- **ALS waveform 状態の確認（ALS 固有・重要）**:
  - Optimize Waveform を**かけない**（バグ）。かかっていれば **Reset Waveform** で raw command AO に戻す。
  - `als_ref` を取る回（§6）は **Monitor Scanner Feedback ON**（`.scnnr.dat` を出すため）。go/no-go の純粋な競合切り分け回は OFF でもよい（§3 で選択）。
- **AI レンジ**: WG 0/5 V TTL は vDAQ 低速 AI レンジ内（不変）。
- **Data Recorder device** が Resource Configuration に居ること（galvo 段のまま）。

---

## 3. ScanImage 設定（galvo からの差分のみ）

不変部（UF 登録・Auto Start・HDF5 レイアウト）は SOP §2 のまま。**変える/確認するのは下記**。

### 3.1 imaging mode
- **ALS（Arbitrary Line Scanning）に切替**。次回の**単一ヘッドライン**（single line）を使う。light/dark・2-line への拡張は別回。
- Optimize Waveform 不使用（§2）。bidirectional の有無は als_ref 突合（P2・offset pre/post）に効くので**設定値を §9 に記録**。

### 3.2 trigger 設定（`syncControlPanel` → Apply to base）
```matlab
syncTriggers = struct('name','injector','wg','Trig Legato130', ...
                      'delaySec',2,'pulseSec',0.2,'enabled',true);
% ALS は delaySec（秒・recorder 起点）で指定。targetFrame は使わない（§1-4）。
```

### 3.3 User Function（不変・必ず確認）
| event | function |
|---|---|
| `acqModeStart` | `syncArmStart`（1 回だけ arm） |
| `acqAbort` / `acqDone` | `syncDisarm`（タイマ掃除＋全 WG 線 LOW） |

- **`frameAcquired` は空**（overflow 回避の要）。ALS でも別 UF が紛れていないか開始前に確認。

### 3.4 Data Recorder 設定
- **Add Signal**: `AI7` → Name `Legato130_TTL`（必須・t0）。`AI6`→`frame_clock` は任意（ALS では flat・§1-2）。
- **Sample Rate**: **5000 Hz**（galvo 段の採用値に合わせる。SOP 本文の "まず 1000 Hz" は galvo bench 前の旧値で、現行は 5000＝実下限 3052 Hz）。同値にしておくと galvo の数値と直接比較できる。
- **Sample Duration**: `Inf`。**Auto Start**: ON（＝common acq-start）。**Use Trigger**: OFF。
- **File Basename / Directory**: ALS imaging と**同 stem**で `raw/` に落ちるよう設定（今は temp_data_recorder なら、少なくとも stem を ALS 取得名に揃える。本番前に `raw/` 化は status §2 の宿題）。

---

## 4. 実行 step-by-step

各回**短時間 grab**。go/no-go 回 → als_ref 回（§6）の順。

1. ALS mode・単一ヘッドライン・line rate を妥当値に（resonant のような ≤33 Hz 制約は ALS では line-scan 設定の問題なので、cycle time を §9 に記録）。Optimize Waveform 不使用を確認。
2. **Grab 開始** → Data Recorder widget が `Start`→`Stop` 表示（Auto Start 動作）を目視。
3. `delaySec`（既定 2 s）後に injector ON→OFF。console に `[sync] injector ON` / `OFF`。
4. **Grab 終了** → Data Recorder 停止 → `.h5` 出力。ALS 側は `.meta.txt` / `.pmt.dat` / `.scnnr.dat`（stem 共通）が出る。
5. §9 に記録: mode=ALS / line 設定（本数・cycle time・bidirectional）/ ALS stem / Data Recorder file 名 / Monitor Scanner Feedback ON/OFF。
6. **abort テスト 1 回**: grab 中に Abort → `syncDisarm` で injector 線が LOW に戻る（stuck-high 無し）を確認。

---

## 5. その場確認（go/no-go 3 点・ALS 版）

- **①** MATLAB console / ScanImage に `Frame queue overflow` が**出ない**こと。出たら `frameAcquired` に UF が残っていないかを最初に疑う。
- **②** Data Recorder の **View** で `Legato130_TTL` にパルスが見える。**かつ ALS line-scan が破綻・取りこぼし・ハングしていない**（= device 競合なし）。競合の兆候があれば §8 fallback へ。
- **③** **frame パルスが無い**ので、§7 のオフラインで `als_datafile_timing` 整列を確認。その場では「両ファイルが出た・サイズが想定どおり」までで可（精緻な整列は offline）。
  - resonant と違い `D2.1` Aux→TIFF クロスチェックは ALS では使わない（ALS は TIFF を吐かない）。

---

## 6. als_ref export（P2 用・Track-W B）

go/no-go とは**別目的**（P2 のオフライン突合用の MATLAB 参照）。同じ ALS セッションで取れる。

- **回の取り方（推奨）**: まず §3–§5 を **Monitor Scanner Feedback OFF** で 1 回（純粋に device 競合と TTL 記録を切り分け）。競合無しを確認したら、**Monitor Scanner Feedback ON** で同条件をもう 1 回 grab（injector＋Data Recorder も並走のまま）。後者が **als_ref＋sync を同時に取れる**理想回。
  - 競合が出ない確証があれば最初から ON 1 回でまとめてよい（時間節約）。判断は §8。
- **なぜ ON か**: Optimize Waveform バグで command AO は当てにできず、**`.scnnr.dat`（実スキャナ位置）が真値**。ON でないと feedback が記録されず P2 の参照にならない。
- **MATLAB 側 export**（stem は §9 に記録した ALS stem）:
```matlab
% 戻り値の数・名前は手元の ScanImage 版の readLineScanDataFiles に合わせて確認すること
out = scanimage.util.readLineScanDataFiles('<als_stem>');   % header / pmtData / scannerPosData 等
save('als_ref_<als_stem>.mat','-struct','out');             % or 個別変数で save
```
- **P2 突合の観点（roadmap §4 Track-W B / handoff §2-2）**:
  - **feedback ×12.5 補間**: feedback は ~400 samp/cycle、PMT は ~5000 samp/cycle → feedback を PMT グリッドに upsample。
  - **offset の pre/post** を `readLineScanDataFiles` と 1 acquisition で突合。
  - **bidirectional** は方向交互の扱い（往復で反転）を確認。
  - `als_loader.py` 出力 vs als_ref を数値一致まで（offline・解析 PC ivwib env）。

---

## 7. オフライン検証（最小フロー）

### 7.1 injector t0（取得 PC quicklook も可・依存 numpy+h5py のみ）
```bash
python datarecorder_loader.py raw/<als_basename>_00001.h5 Legato130_TTL
# 期待: samplerate 5000 / injector t0 = <idx/fs> s (1 edge)
#       frame_clock を録っていない or flat → "frame_clock absent (expected for ALS)" / n_frames=0 が正
```

### 7.2 als_datafile_timing 整列（go/no-go ③ の数値化）
- Data Recorder `.h5` と ALS データファイルは **common acq-start で同一起点を共有**（Auto Start）。
- `readLineScanDataFiles` で ALS 側の cycle/sample タイムライン（取得開始起点）を得る。
- recorder-relative な injector t0 を、この共有起点を介して ALS の cycle/sample に写像。
- **residual offset（recorder-start − ALS 取得開始）を出す**＝ ALS 版 head_pad。これが小さく安定なら ③ PASS。大きい/ばらつくなら §8。
- 物理到達遅延は別（`physical_delay_offset_s`・下流加算・t0 に折り込まない）。

---

## 8. 判定と次手 / FAIL fallback

**PASS（①②③）** →
- ALS の HDF5 レイアウト＝galvo と同一（`Legato130_TTL`＝t0・`frame_clock` は ALS で flat/省略）を確認。
- als_datafile_timing 整列が数値で成立（residual offset を記録）。
- 次は **resonant 段**（SOP §3・`D2.1` Aux→TIFF を任意クロスチェックに復活）。3 mode 揃いで `trigger_sync.schema.json` finalize。
- 並行で **P2**（§6 で als_ref が取れていれば als_loader 突合へ）。

**FAIL → fallback**

| 症状 | 切り分け |
|---|---|
| overflow が出る | `frameAcquired` に UF が残っていないか（syncArmStart は acqModeStart のみ） |
| TTL が載らない | AI レンジ/配線/WG 出力（writeLineToVal）/ Data Recorder の signal が AI7 か |
| **ALS と Data Recorder が競合**（line-scan 破綻・ハング・データ破損） | mode 別に切り分け。Sample Rate を下げて再試行。device 競合なら **sync_architecture §4.5 の階層判断**（ALS+Recorder+injector は全て T1 vDAQ-native＝同一クロック前提。競合が本質的なら T2/T3 へ退避を検討） |
| **als_datafile_timing 整列がゆるい/ばらつく**（residual offset が大きい・不安定） | common acq-start の同期精度の問題。フォールバック検討: ALS の line/cycle period clock を AI に録って **frame_clock 相当の内部アンカー**にできるか（ScanImage が line-scan で period clock を吐くかを確認・要検証）。判断は sync_architecture §2 に戻す |
| Monitor Scanner Feedback ON で競合 | als_ref 回を OFF の go/no-go 回と分離（§6）。ON 回だけ Sample Rate を下げる |

---

## 9. 記録欄（このランで埋める）

```
date:                 2026-06-__
imaging mode:         ALS (single head line)
line config:          本数=__  cycle_time=__  bidirectional=__  optimize_waveform=OFF(reset)
monitor_scanner_fb:   OFF / ON   （ON 回 = als_ref）
delaySec / pulseSec:  2 / 0.2
sample_rate_hz:       5000
ALS stem:             sub-..._run-..._00001   (.meta.txt/.pmt.dat/.scnnr.dat)
datarecorder_file:    raw/..._00001.h5
--- go/no-go ---
① overflow:           無 / 有(__)
② injector TTL:       見える / 見えない    device 競合: 無 / 有(__)
③ als_datafile_timing: injector t0 = __ s (sample __)  residual offset(ALS head_pad) = __ s
abort test:           injector LOW 復帰 OK / NG
--- P2 (als_ref があれば) ---
readLineScanDataFiles: OK / NG     feedback ×12.5 upsample: __   offset pre/post: __   bidirectional: __
```

### trigger_sync（ALS）sidecar スケルトン — schema 最小 VALID 形
> 値を §9 の実測で埋める。`anchor` は `als_datafile_timing` 固定（schema が強制）・`frame_timebase` は省く・`signals.frame_clock` は null。

```json
{
  "schema_version": "0.1.0",
  "scan_mode": "als",
  "samplerate_hz": 5000.0,
  "datarecorder_file": "<..._00001.h5>",
  "als_datafile": "<..._00001>",
  "signals": {
    "injector_ttl": "Legato130_TTL",
    "frame_clock": null
  },
  "t0": {
    "source": "datarecorder_ttl_edge",
    "dataset": "Legato130_TTL",
    "edge": "rising",
    "threshold_v": 2.5,
    "sample_index": 0,
    "t0_recorder_s": 0.0,
    "n_edges": 1
  },
  "anchor": "als_datafile_timing",
  "physical_delay_offset_s": null
}
```

---

## 関連ドキュメント

- 親 SOP（正本・3-mode generic）: `microscope_control_dev/docs/method_a_e2e_gonogo_sop.md`
- 同期設計の正本: `microscope_control_dev/docs/sync_architecture.md`（§2 anchor / §4.5 device 階層 / §6 recipe）
- 取得側 status: `microscope_control_dev/docs/status.md`（§2 Tier 順 / §3.5 injector）
- 契約 schema: `trigger_sync.schema.json`（ALS 最小インスタンス VALID 済）
- loader: `microscope_control_dev/src/python/datarecorder_loader.py`（兄弟＝`als_loader.py`）
- 優先順位の正: `in_vivo_water_imaging_brain/docs/strategy_roadmap.md`（§4 Tier0 / §5 gate / §4 Track-W B）
