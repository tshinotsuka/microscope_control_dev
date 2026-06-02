# microscope_control_dev

SRS 脳内水動態イメージング研究の**取得側**（顕微鏡制御・取得開発）リポジトリ。
ScanImage + vDAQ 環境のセットアップ、設定（MDF / CFG / 配線）、操作手順、取得用コードを管理する。

> **Stage 1 ドラフト** — 初回 ALS テスト取得の成功後に、`config/` への baseline 取り込みと
> README 最終化を行う（下記「現状」参照）。

## 関連プロジェクト

| project_id | 役割 | 環境 |
|---|---|---|
| `microscope_control_dev` | 取得開発・テスト・キャリブレーション（本リポジトリ） | Windows / ScanImage |
| `2025_brain_water_dynamics` | 本実験データ取得 | Windows / ScanImage |
| `in_vivo_water_imaging_brain` | 解析側・命名規則 / metadata スキーマの原典 | Linux |

命名規則と metadata スキーマは**全 project 共通**で、`project_id` で分離する。
取得した raw data は解析側 project の規則に機械的に接続できる形で出力する
（`sops/scanimage_logfilestem_sop.md` 参照）。

## データレス方針

解析側と同じく、本リポジトリは**生データを持たない**。追跡するのは設定・手順・コード・設計文書のみ。

- 除外（`.gitignore`）: raw data（`*.tif` / `*.pmt.dat` / `*.scnnr.dat` / `*.meta.txt`）→ NAS に保管
- 追跡: 設定成果物（ScanImage CFG / `.roigrp` / MDF の `.m`）、手順、コード、文書

## 構成

```
docs/      仕様・設計・概要・トラブルシュート（参照用）
sops/      操作手順書（撮影時に見るチェックリスト）
config/    MDF / ScanImage CFG / 配線マップ
src/       コード（ScanImage / DAQ / MATLAB / Arduino）
examples/  サンプル・参照データ片
templates/ 雛形
```

## 現状（Phase 1）

| Done criteria | 状態 |
|---|---|
| 10 frames 以上の TIFF 保存 | ✅ |
| PMT 3ch 同時取得 | ✅ |
| metadata から frame rate / zoom / channel / FOV | ✅ |
| 再起動後も同じ構成で起動 | ✅ |
| Galvo waveform calibration | ✅ 部分達成（Calibrate + Test。Optimize はベンダーバグで scope 外） |
| baseline MDF / CFG が Git 管理されている | ⏳ 本リポジトリで対応中 |

詳細・既知の問題は `docs/overview.md` と `docs/troubleshooting.md` を参照。
