# ScanImage logFileStem 設定 SOP

撮影時に正しい命名規則で raw data を出力するための標準作業手順書。
取得後のリネーム作業をゼロにし、解析側 project と機械的に接続できる raw data を
生成することを目的とする。

依拠する規則:

- `in_vivo_water_imaging_brain/docs/file_naming.md`(解析側 project・命名規則の原典。2026-06-02 に v3 凍結)
- `in_vivo_water_imaging_brain/docs/metadata_schema.md`(解析側 project・metadata 契約)
- `docs/status.md`(取得側 living 文書・現在状態の正)
- `docs/overview.md`(取得側システム構成)

---

## 1. 撮影前に決めること

### 1.1 project_id を選ぶ

| 状況 | project_id |
|---|---|
| 本実験(in vivo imaging、D2O 取得など) | `2025_brain_water_dynamics` |
| 開発・テスト・キャリブレーション(ALS テスト、ファントム等) | `2026_microscope_control_dev` |

> project_id は `<YYYY>_<theme>` 形式（nas_structure.md）。dev/test も以降は `2026_microscope_control_dev` で統一する
> （リポジトリ名 `microscope_control_dev` とは別物）。以前 `microscope_control_dev` で置いた dev データは
> raw リネーム禁止の原則どおり**そのまま**にし、新規分から新 id を使う。

### 1.2 dataset_id を決める

形式: `<YYYYMMDD>_sub-<mouseID>_ses-<XX>`

- `<YYYYMMDD>`: 撮影日(例: `20260529`)
- `<mouseID>`: マウス ID(例: `sk8`)。個体に紐づかない参照測定の場合は `ref`
- `<XX>`: その日のセッション番号(`01`, `02`, ...)

例:

- 本実験: `20260529_sub-sk8_ses-01`
- 開発テスト: `20260529_sub-ref_ses-01`

### 1.3 保存先フォルダを取得 PC ローカルに作成

```
<取得 PC ローカル root>/<project_id>/<modality>/<dataset_id>/raw/
```

例(開発テスト):

```
D:\experiment_data\2026_microscope_control_dev\2photon\20260529_sub-ref_ses-01\raw\
```

例(本実験):

```
D:\experiment_data\2025_brain_water_dynamics\2photon\20260YYMM_sub-sk8_ses-01\raw\
```

**注意**: NAS に直書きしない。撮影は必ずローカル → 撮影後に rsync で NAS に転送。

---

## 2. ScanImage 設定

撮影開始前に以下を設定:

| 項目 | 設定値 | 備考 |
|---|---|---|
| Save Path | 上記の `raw/` 直下 | NAS 直書き禁止 |
| File Stem (`logFileStem`) | `sub-<mouseID>_ses-<XX>_cond-<condition>_run-<XX>` | `fov-` は必要時に挿入 |
| Acquisition Counter | ScanImage 自動付与 | 人間は触らない |
| Scanner Feedback (`.scnnr.dat`) | **ON** | ALS 撮影時は必須(file_naming.md「ALS の出力命名」) |
| Channel Logging | ON | 必要 channel 数 active |

### File Stem の構成例

| 状況 | logFileStem の値 |
|---|---|
| in vivo、baseline 条件、1 回目 | `sub-sk8_ses-01_cond-baseline_run-01` |
| D2O 静脈内投与後 | `sub-sk8_ses-01_cond-d2oiv_run-01` |
| FOV を切り替えた | `sub-sk8_ses-01_fov-02_cond-baseline_run-01` |
| 固定 EGFP slice での ALS テスト | `sub-ref_ses-01_cond-qc_run-01` |

> **cond は v3 文法に従う**（file_naming.md と同期）:
> - **数値は cond に入れない**。`100d2o` は廃止 → `d2oiv`（濃度は metadata `sample.injections[].concentration_pct`）。
> - **試料属性は cond に入れない**。`egfp`/`slice`/`fixed` は cond に密輸せず、`cond-qc`（または `cond-test`）の 1 語にして
>   属性は metadata（`sample.preparation: slice` / `channels[].marker: GFP` / `subject.genotype`）へ。
>   旧 `cond-egfp-slice` のような token は不可。

撮影実行後、ScanImage は連番(`_00001`, `_00002`, ...)を自動で付けて出力する。

---

## 3. 撮影中の更新タイミング

ScanImage 側で `logFileStem` を更新するタイミング:

### 3.1 `run-` の +1

`run-` は **独立した別 take** のときだけ +1 する（人間が割り当てる取得番号）。

- 同 condition で独立した取得を繰り返すとき（別 trial など）。今後使う可能性があれば最初から `run-01`。
- **scan mode 切替（raster ↔ ALS）や scan speed 変更では +1 しない**。ScanImage は grab ごとに連番 `_NNNNN` を増やすので、
  同一 `run-` の中に raster grab と複数の ALS grab が同居してよい（file_naming.md v3）。
- acquisition の識別キーは **(fov, cond, run, idx)** で **1 idx(=`_NNNNN`)= 1 acquisition**。
  raster/ALS・scan speed・cycle 数の違いは `run-` でなく metadata で表す。
- baseline → 処置で条件が変わるときは `cond-` が状態を担い、**`run-` は cond ごとに 01 にリセット**（§3.2）。

### 3.2 `cond-` の変更

- 実験条件が変わったとき(`baseline` → `d2oiv` など)。**cond が変わったら `run-` は 01 にリセット**する。
- **内容ベース**で命名(`control` / `100d2o` のような廃止語・曖昧語は使わない。濃度などの数値は metadata)。

### 3.3 `fov-` の挿入

- 同セッション内で意図的に FOV を変えたとき
- `fov-` は必要な時だけ入れる(常時入れる必要なし)

### 3.4 連番(`_00001`)

- ScanImage に任せる、人間は触らない
- stem を変えれば自動でリセットされるはず(実機で挙動確認 → §6 TODO)

### 3.5 入れない要素(重要)

以下は **ファイル名に入れない**。metadata で扱う(file_naming.md「acquisition_type / scanner_type はファイル名に入れない」/ metadata_schema.md):

- acquisition_type(`frame` / `zstack` / `volume` / `als`)
- scanner_type(`galvo` / `resonant`)
- scan_mode(`raster` / `als`)

理由: ScanImage が取得時に既に知っている情報。ファイル名に入れると二重持ちになり
取得時のオペミスを生む。metadata から自動判定する方が堅牢。

---

## 4. 撮影後

### 4.1 ファイル名の目視確認

`raw/` 配下のファイルが規則どおりか確認。**間違っていてもリネームしない**
(取得時に正しく付けるのが大原則、file_naming.md「設計方針」：取得時に正しく付ける > 取得後にリネーム)。

リネームせず、可能なら metadata 側の補足で対応する。誤命名が大きな問題なら、
撮影をやり直す判断を検討。

### 4.2 ALS 撮影時の追加確認

- `.meta.txt` + `.pmt.dat` + `.scnnr.dat` の 3 ファイルが揃っているか
- `.scnnr.dat` が空でないか(scanner feedback が実際に記録されているか)

### 4.3 metadata.yaml 生成

解析側 project の `generate_metadata.py` を走らせる:

```bash
python generate_metadata.py <dataset_path>
```

→ `raw/metadata.yaml` が生成される。ScanImage TIFF から自動取得される項目はそのまま入る。

### 4.4 手入力フィールドを埋める

`raw/metadata.yaml` の以下を人間が記入:

- mouse の生物的情報(genotype, sex, age)
- 投与条件(D2O concentration, dose, timing)
- 麻酔・手術条件
- 実験意図・観察記録

### 4.5 NAS への転送

撮影セッション終了後、NAS にミラー:

```bash
rsync -av <ローカル dataset path>/ <NAS 上の同 path>/
```

NAS が一次保管。ローカルは作業終了後に削除可能。

---

## 5. チェックリスト(撮影直前用、コピペ運用)

```text
- [ ] project_id を選んだ(本実験 / 開発)
- [ ] dataset_id を決めた(<YYYYMMDD>_sub-<mouseID>_ses-<XX>)
- [ ] 保存先フォルダをローカルに作成
- [ ] ScanImage の Save Path をその raw/ に設定
- [ ] logFileStem を sub-<mouseID>_ses-<XX>_cond-<cond>_run-<XX> に設定
- [ ] 前回の cond-/run- が残っていないか確認(更新忘れ防止)
- [ ] Scanner Feedback (.scnnr.dat) を ON(ALS 時は必須)
- [ ] 必要 channel が logging enable になっている
- [ ] NAS に直書きしていない(必ずローカル)
```

---

## 6. 実機で詰める TODO

このセクションは実機検証で埋める:

- [ ] ScanImage GUI 上で `logFileStem` を設定する具体的なパネル名・場所
      (version によって異なる可能性)
- [ ] 連番のリセット挙動: `logFileStem` を変更したら自動で `_00001` に戻るか?
- [ ] MATLAB から直接更新するコマンド
      (`hSI.hScan2D.logFileStem = '...'` 等)が GUI と一致して動くか
- [ ] ALS 撮影時の `.scnnr.dat` enable 設定の場所
- [ ] multi-channel + multi-ROI + FastZ の組み合わせで stem 挙動が変わらないか
- [ ] 取得 PC のローカル保存先 root(`D:\` か別 drive か)を確定

---

## 7. 関連文書

- 命名規則の原典: `in_vivo_water_imaging_brain/docs/file_naming.md`
- metadata スキーマ: `in_vivo_water_imaging_brain/docs/metadata_schema.md`
- 自動取得スクリプト: `in_vivo_water_imaging_brain/scripts/generate_metadata.py`
- NAS 構造: `in_vivo_water_imaging_brain/docs/nas_structure.md`
- 取得側の現在状態(living): `docs/status.md`
- 取得側システム構成: `docs/overview.md`

---

初版 2026-05-29、`microscope_control_dev` project セットアップ時。

改訂 2026-06-04: 解析側 `file_naming.md` v3（2026-06-02 凍結）と同期。`cond-100d2o` → `d2oiv`（濃度は metadata）、
`cond-egfp-slice` → `cond-qc`（属性は metadata）、`run-` の +1 規則を「独立 take のみ・raster↔ALS では増やさない・
識別キー (fov,cond,run,idx)」に訂正、cond 変更時の `run-` リセットを明記、廃止された `handoff_hardware_control_dev.md`
参照を `status.md` / `overview.md` / `metadata_schema.md` に張り替え。

改訂 2026-06-04: dev/test の project_id を `microscope_control_dev` → `2026_microscope_control_dev` に変更（`<YYYY>_<theme>` 準拠）。
以降の新規 dev/test データはこの id を使う。既存 dev データはリネームしない。
