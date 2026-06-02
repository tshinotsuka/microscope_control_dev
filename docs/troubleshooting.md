# Troubleshooting — microscope_control_dev

ScanImage + vDAQ 環境で遭遇した問題と対処の記録。
新しい問題が出たら下の「記録フォーマット」に従って追記する。

最終更新: 2026-06-01

---

## 記録フォーマット

各項目は以下を埋める。

- **現象**: 観察された挙動
- **原因**: 判明した / 推定される原因
- **対処**: 解決策 or 回避策
- **状態**: `resolved` / `workaround` / `vendor_issue` / `under_investigation`

---

## アクティブ / 直近の問題

### Optimize Waveform が実行不能

- **現象**: Waveform Controls の Optimize Waveform を実行すると失敗する。
  - 1回目: `Tracking error unexpectedly increased. Optimization stopped to prevent damage to actuator.`(最適化が発散)
  - 2回目以降(Reset後): `関数または変数 'feedbackPoints' が認識されません`(MATLAB エラー)が再現
- **原因**: ScanImage Premium 2026.0.0 (build 67620ca4cc) の内部状態管理バグと推定。Calibrate Galvo Feedback と Optimize の間のデータ引き渡し不全の可能性。
- **試した対策(すべて効果なし)**:
  - Sample Window Size 1 → 5
  - Optimization Iterations 6 → 4
  - Line time 1 ms → 2 ms
  - Calibrate Galvo Feedback 再実行(X/Y とも "done!" は出る)
  - Reset Waveform → Refresh Waveforms
  - ScanImage 完全再起動
- **対処(回避策)**: Optimize Waveform はスキップ。**Calibrate Galvo Feedback 成功 + Test Waveform で feedback 確認**を運用上の合格ラインとする。実位置は `.scnnr.dat` に記録されるので、必要なら後処理で command vs actual を評価する。
- **状態**: `vendor_issue`(MBF case 25850 の続報として報告予定。repro スクショ保存済み)

### "Generated AO is empty" エラー

- **現象**: optimization 試行中などにコマンドウィンドウへ
  `Generated AO is empty. Ensure that there are active ROIs with scanfields that exist in the current Z series.` が頻発。
- **原因**: 未確定。ROI / scanfield / Z series 設定の不整合(設定起因)か、上記 Optimize バグの副作用かを切り分け中。
- **対処**: ALS の ROI を正しく組んだ状態で再現するかを確認して切り分ける(設定起因なら消えるはず)。判定結果次第で MBF 報告に含めるか決める。
- **状態**: `under_investigation`

### 自作PD Ch2 の斜め波状ノイズ

- **現象**: 当初、自作PD を入れた Ch2(vDAQ 高速入力 AI2)のみに斜め波状のうねりが見えた。PMT の Ch0/Ch1/Ch3 には出なかった。
- **原因**: 当初は vDAQ 移行で加わった Ch2 固有の電気的問題(インピーダンス不整合 / グラウンドループ / シールド不足)を想定。
- **対処**: 再確認したところアーティファクトは再現せず、信号は許容範囲だった。**ハードウェア変更は実施していない**。
- **状態**: `resolved`(再確認により問題なしと判断。再発時はインピーダンス整合・50Ω終端・GND経路・電源系統を切り分ける)

---

## 解決済み(PC 移行時)

新 PC への ScanImage + vDAQ 移行で遭遇し、解決済みの問題。

| # | 現象 | 原因 / 対処 |
|---|---|---|
| 1 | vDAQ が認識されない | 電源ケーブル未接続 → 6 ピン PCIe 電源を接続して認識 |
| 2 | ドライバインストール失敗 | `rdi.inf` を直接インストールして解決 |
| 3 | MATLAB R2026a で互換性問題 | R2025b へダウングレード |
| 4 | ライセンス Error 210 | MBF サポート(case 25850, Sam Ventura 氏)が新キー発行 |
| 5 | highlightWidgets エラー | MATLAB ダウングレードで解決(#3 と同根) |
| 6 | PMT2100 ソフトがフォルダコピーで動かない | USB ドライバ / レジストリ / VISA 設定がインストーラ依存。**専用インストーラ必須**(NI-VISA 18.5 同梱) |
| 7 | PMT2100 ソフトと ScanImage が同時に USB を掴めない | 切替時は対象を完全終了(タスクマネージャでプロセス消滅まで確認) |
| 8 | Focus で画像の上半分しか更新されない | **Stripe Display のチェックを外す**(データ取得は正常、ライブ描画のみの問題) |
| 9 | 起動失敗(lastUsrFile / wb / PCIe_6374 エラー) | 旧 PC の NI DAQ 用 CFG を起動時に自動読込していたのが真因。launch 画面で旧 CFG を読まずに起動 → Save Configuration As で新 CFG を保存し以後それを使う。旧 CFG は退避 / リネーム |
| 10 | classData が壊れる / 起動中に見えない | classData は終了時に書き出される。壊れた場合は ConfigData フォルダ退避でリセット可(要注意操作) |
| 11 | objectiveResolution 1 ↔ 15 の混乱 | 表示スケールが変わるだけ。画像取得の可否や縞には無関係 |

---

## 連絡先

- MBF Bioscience サポート: support@mbfbioscience.com
- 担当: Sam Ventura(Software and Support Engineer)
- 既存ケース: 25850

---

## 関連文書

- `config/wiring/vdaq_io_map.yaml` — I/O 割当の現状
- `sops/scanimage_startup.md` — 起動手順(未作成)
- `sops/calibrate_galvo_feedback.md` — feedback calibration 手順(ALS テスト後に作成)
