# Overview — microscope_control_dev

取得側プロジェクトの現状と Phase 構造をまとめた参照文書。

最終更新: 2026-06-02（Stage 1 ドラフト）

---

## 1. 目的

SRS 脳内水動態イメージング研究の取得側。
顕微鏡（ScanImage + vDAQ）の制御・設定・取得手順・コードを開発し、
本実験 project `2025_brain_water_dynamics` で再現可能な取得基盤を整える。

解析側 project `in_vivo_water_imaging_brain` が命名規則・metadata スキーマの原典で、
本リポジトリはその規則に従う raw data を出力する側に当たる。

## 2. 現在のシステム構成

| 項目 | 値 |
|---|---|
| OS | Windows 11 |
| MATLAB | R2025b |
| 取得ソフト | ScanImage Premium 2026.0.0 (build 67620ca4cc) |
| DAQ | vDAQ (Kintex UltraScale, PCIe) |
| スキャン系 | galvo-galvo |
| 検出器 | PMT2100 × 3（Ch0 / Ch1 / Ch3）+ 自作フォトダイオード（Ch2） |
| 高速入力 | 4ch, 125 MS/s（画像化信号用） |
| 低速入力 | 12ch, 最大 500 kHz（補助 / behavior） |

詳細な I/O 割当は `config/wiring/vdaq_io_map.yaml`。

## 3. Phase 構造

別チャネルで策定した Phase 1–6 構造を採用。各 Phase の Done criteria 全文は順次転記する。

### Phase 1 — 基本取得基盤（ほぼ完了）

| Done criteria | 状態 |
|---|---|
| 10 frames 以上の TIFF 保存 | ✅ |
| PMT 3ch 同時取得 | ✅ |
| metadata から frame rate / zoom / channel / FOV 取得 | ✅ |
| 再起動後も同じ構成で起動 | ✅ |
| Galvo waveform calibration | ✅ 部分達成 |
| baseline MDF / CFG が Git 管理 | ⏳ 本リポジトリ立ち上げで対応中 |

- Galvo calibration は **Calibrate Galvo Feedback + Test Waveform** までを運用上の合格ラインとする。
  Optimize Waveform は ScanImage 2026.0.0 のベンダーバグで実行不能のため scope 外
  （`docs/troubleshooting.md` 参照、MBF case 25850）。実位置は `.scnnr.dat` に記録される。
- Phase 1 の残タスクは実質「repo 立ち上げ」のみ。

### Phase 2 以降（TBD）

- SRS 取得（自作 PD Ch2 系）、ALS マルチライン、FastZ / injector / behavior 同期、resonant 等を含む。
- 各 Phase の定義・Done criteria は別チャネル計画書から順次転記する。

## 4. 既知の問題

`docs/troubleshooting.md` に集約。直近のアクティブ項目:

- Optimize Waveform 実行不能（`vendor_issue`、MBF case 25850 で報告予定）
- "Generated AO is empty"（`under_investigation`）

## 5. 関連文書

- `sops/scanimage_logfilestem_sop.md` — 命名規則に沿った取得手順
- `config/wiring/vdaq_io_map.yaml` — I/O 割当
- `docs/troubleshooting.md` — 問題と対処
- 解析側: `in_vivo_water_imaging_brain/docs/{file_naming,metadata_schema,nas_structure}.md`
