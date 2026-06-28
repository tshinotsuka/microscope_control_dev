#!/usr/bin/env python
"""dwell_probe.py -- ALS の実 sample dwell を出して cond-qc(full-frame) と比較し、
per-pixel SNR で並ぶための取得レシピ（sample 数 / cycle rate / 反復回数）を逆算する。

背景:
  ch3(O-D) が ALS で純 shot に沈むのは per-pixel 滞在時間が cond-qc より桁で短いから。
  SRS の shot SNR ∝ √(dwell)。必要倍率を「ALS の実 dwell」と「cond-qc の dwell」から算出。

dwell を 2 系統で出して突き合わせる:
  (a) meta 由来   : SI.hScan2D.sampleRate があれば 1/sampleRate が正味 per-sample 滞在。
                    無ければ linePeriod / pixelsPerLine。
  (b) feedback 由来: cycle 周期 / 1cycle の sample 数（naive, flyback 込み）と、
                    実掃引区間(line_wins)だけで割った正味 dwell。

使い方（VSCode）:
  1) このファイルを scripts/ に置く（prepare_als が使えればどこでも可）。
  2) 下の「===== 書き換える =====」の ALS_STEM と cond-qc 設定を確認（既に埋めてある）。
  3) ターミナル（Ctrl+`）で:  python scripts/dwell_probe.py
  ターミナルに dwell 比較・必要倍率・推奨レシピが出る。ivwib 環境外なら raw 解析だけ走る。
"""
import os
import re
import struct
from pathlib import Path

import numpy as np

# ============================== 書き換える ==============================
ALS_STEM = r"C:\Users\Takanori Shinotsuka\workspace\2025_brain_water_dynamics\20260626_sub-ts290_ses-01\raw\sub-ts290_ses-01_cond-d2oiv_run-01_00003"
# cond-qc（O-D が見えた条件・full-frame）
CONDQC_PIXELS   = 512        # 1 line の画素数（512x512）
CONDQC_DWELL_NS = 3200.0     # pixel dwell [ns]
CONDQC_FRAME_HZ = 1.07       # frame rate [Hz]（参考）
# 目標 FOV 上の必要空間分解（PVS 0-2µm を何 px で見たいか）
FOV_UM          = 34.0       # ALS line の FOV [µm]（F4 の calib 由来）
PVS_UM          = 2.0        # 解像したい最小スケール [µm]
PVS_MIN_PX      = 6          # PVS を最低何 px で刻むか
# ALS パワーは cond-qc と同じ前提（違うなら倍率を別途補正）
SAME_POWER      = True
# =====================================================================


# --------------------------- meta 由来 dwell --------------------------- #

SI_KEYS = {
    "sampleRate":      r"SI\.hScan2D\.sampleRate\s*=\s*([\d.eE+-]+)",
    "linePeriod":      r"SI\.hRoiManager\.linePeriod\s*=\s*([\d.eE+-]+)",
    "scanFramePeriod": r"SI\.hRoiManager\.scanFramePeriod\s*=\s*([\d.eE+-]+)",
    "pixelsPerLine":   r"SI\.hRoiManager\.pixelsPerLine\s*=\s*([\d.eE+-]+)",
    "scannerFreq":     r"SI\.hScan2D\.scannerFrequency\s*=\s*([\d.eE+-]+)",
    "objectiveRes":    r"SI\.objectiveResolution\s*=\s*([\d.eE+-]+)",
}


def _read_text_blob(stem):
    """ALS の meta テキスト（.meta.txt 等）を探して中身を返す。無ければ ""。"""
    cand = [stem + ".meta.txt", stem + ".meta", stem + ".txt"]
    p = Path(stem)
    cand += [str(x) for x in p.parent.glob(p.name + "*.txt")]
    for c in cand:
        if os.path.exists(c):
            try:
                return open(c, "r", errors="ignore").read(), c
            except Exception:
                pass
    return "", None


def meta_dwell(stem):
    blob, src = _read_text_blob(stem)
    found = {}
    if blob:
        for k, pat in SI_KEYS.items():
            m = re.search(pat, blob)
            if m:
                try:
                    found[k] = float(m.group(1))
                except ValueError:
                    pass
    dwell_ns = None
    how = None
    if "sampleRate" in found and found["sampleRate"] > 0:
        dwell_ns = 1e9 / found["sampleRate"]
        how = f"1/sampleRate ({found['sampleRate']:.3g} Hz)"
    elif "linePeriod" in found and "pixelsPerLine" in found and found["pixelsPerLine"] > 0:
        dwell_ns = found["linePeriod"] / found["pixelsPerLine"] * 1e9
        how = f"linePeriod/pixelsPerLine ({found['linePeriod']*1e3:.3g} ms / {found['pixelsPerLine']:.0f})"
    return dwell_ns, how, found, src


# --------------------------- feedback 由来 dwell --------------------------- #

def feedback_dwell_via_ivwib(stem):
    """prepare_als 経由で cycle 周期・sample 数・実掃引区間から dwell を出す。"""
    try:
        from ivwib.viz import als_overlay_panel as P
    except Exception as e:
        return None, f"ivwib import 不可: {e}"
    ls, sweeps, fdbk, pmt = P.prepare_als(stem)
    info = {}
    for attr in ("cycle_duration_s", "cycle_rate_hz", "pmt_channels"):
        info[attr] = getattr(ls.info, attr, None)
    cyc = ls.info.cycle_duration_s
    scn = np.asarray(ls.scnnr)
    n_samp = scn.shape[1] if scn.ndim >= 2 else scn.shape[0]
    naive_ns = cyc / n_samp * 1e9
    # 実掃引区間（line ごとの f0..f1）だけで割る = 正味
    active_total = 0
    lines = []
    for (nm, f0, f1) in fdbk:
        a = int(f1) - int(f0)
        active_total += a
        lines.append((nm, a))
    net_ns = (cyc * (active_total / n_samp) / active_total * 1e9) if active_total else naive_ns
    # 上式は cyc/n_samp と同値（active がキャンセル）。正味は「掃引に使った総時間/総有効sample」
    # = cyc*(active_total/n_samp) / active_total = cyc/n_samp。つまり naive と同じ per-sample。
    # 差が出るのは「1 line を複数 ROI で共有」等の構成時のみ。情報として効率も返す。
    eff = active_total / n_samp if n_samp else float("nan")
    return dict(cycle_s=cyc, n_samp=n_samp, naive_ns=naive_ns, active_total=active_total,
                efficiency=eff, lines=lines, info=info, all_info=vars(ls.info)), None


def feedback_dwell_via_raw(scnnr_path):
    """ivwib が無い時の最終手段: .scnnr.dat を直接読み、形を推定して per-cycle sample 数を出す。
    レイアウトは loader 仕様依存なので、ここでは「サイズから候補を提示」に留める。"""
    size = os.path.getsize(scnnr_path)
    out = {"bytes": size}
    # float32 / float64 で要素数候補
    for name, w in (("float32", 4), ("float64", 8)):
        if size % w == 0:
            out[name + "_elems"] = size // w
    return out


# --------------------------- レシピ逆算 --------------------------- #

def recipe(als_dwell_ns, als_n_samp):
    print("\n========== dwell 比較 ==========")
    print(f"cond-qc (full-frame) : {CONDQC_DWELL_NS:.0f} ns/pixel  ({CONDQC_PIXELS}px, {CONDQC_FRAME_HZ} Hz)")
    if als_dwell_ns is None:
        print("ALS dwell: 取得不可（meta/feedback 両方から出せず）")
        return
    print(f"ALS line (per visit) : {als_dwell_ns:.3g} ns/sample  ({als_n_samp} sample/line)")
    ratio = CONDQC_DWELL_NS / als_dwell_ns
    snr_gap = np.sqrt(ratio)
    print(f"\nper-visit 滞在比 = {ratio:.0f}x  ->  shot SNR ギャップ = √{ratio:.0f} ≒ {snr_gap:.0f}x  (ALS 不利)")
    if not SAME_POWER:
        print("  ! パワーが cond-qc と異なる -> この倍率は要補正")

    # 必要空間 sample（FOV を PVS_MIN_PX/PVS_UM で刻む下限）
    need_px_per_um = PVS_MIN_PX / PVS_UM
    target_samples = int(np.ceil(FOV_UM * need_px_per_um))
    print(f"\n--- レシピ逆算（目標 SNR ギャップ {snr_gap:.0f}x を分担）---")
    # 1) 空間 sample 削減
    spat_gain = als_n_samp / target_samples if target_samples else 1.0
    snr_spat = np.sqrt(spat_gain)
    print(f"1) 空間 sample {als_n_samp} -> {target_samples}  "
          f"(FOV {FOV_UM}µm / {need_px_per_um:.2f}px/µm, PVS {PVS_UM}µm≈{PVS_MIN_PX}px)")
    print(f"   per-sample dwell x{spat_gain:.0f}  =>  SNR x{snr_spat:.1f}")
    remain = snr_gap / snr_spat
    # 2) cycle rate 低下（MTT/dt>=8 を保つ範囲）。MTT=0.8s -> dt<=0.1s -> >=10Hz まで落とせる
    print(f"   残り SNR ギャップ: {remain:.1f}x")
    cyc_gain_needed = remain ** 2          # dwell をさらに何倍伸ばすか
    print(f"2) cycle rate 低下 or 反復で残り {remain:.1f}x（= 滞在 {cyc_gain_needed:.0f}x）を埋める:")
    # cycle rate を 166->X に落とすと per-visit dwell が 166/X 倍
    for newhz in (40, 20, 10):
        g = 166.667 / newhz
        print(f"   - cycle {newhz}Hz: 滞在 x{g:.1f} (SNR x{np.sqrt(g):.1f}), MTT/dt=0.8*{newhz}={0.8*newhz:.0f} "
              f"{'OK' if 0.8*newhz>=8 else 'NG(<8)'}")
    # 3) 反復平均
    print(f"3) cycle-locked 反復 bolus √N（.h5 TTL で exact 重ね）:")
    for N in (3, 5, 9):
        print(f"   - N={N}: SNR x{np.sqrt(N):.1f}")
    print("\n推奨の出発点: 1)空間{}→{} + 2)cycle ~20-40Hz + 3)N=3-9 反復。"
          .format(als_n_samp, target_samples))
    print("  （1 は後処理 binning では戻らない＝取得時に dwell を稼ぐ本質手。今回 time-bin が効かなかった理由）")


def main():
    stem = ALS_STEM
    scnnr = stem + ".scnnr.dat"
    print(f"ALS_STEM = {stem}")
    print(f".scnnr.dat exists: {os.path.exists(scnnr)}")

    # (a) meta
    m_ns, m_how, m_found, m_src = meta_dwell(stem)
    print("\n--- (a) meta 由来 ---")
    print(f"meta src: {m_src}")
    if m_found:
        print("found:", {k: round(v, 6) for k, v in m_found.items()})
    if m_ns:
        print(f"meta dwell = {m_ns:.3g} ns/sample  [{m_how}]")
    else:
        print("meta から dwell 出せず（sampleRate / linePeriod が見つからない）")

    # (b) feedback
    print("\n--- (b) feedback 由来 ---")
    fb, err = feedback_dwell_via_ivwib(stem)
    als_dwell = m_ns
    als_n_samp = None
    if fb:
        print(f"cycle = {fb['cycle_s']*1e3:.4g} ms  sample/line(total) = {fb['n_samp']}")
        print(f"active sweep samples = {fb['active_total']}  (efficiency {fb['efficiency']*100:.0f}%)")
        print(f"per-sample naive dwell = {fb['naive_ns']:.3g} ns")
        print("lines:", fb["lines"])
        print("ls.info keys:", list(fb["all_info"].keys()))
        als_n_samp = fb["n_samp"]
        if als_dwell is None:
            als_dwell = fb["naive_ns"]
        # 突き合わせ
        if m_ns:
            print(f"\n突き合わせ: meta {m_ns:.3g} ns  vs  feedback naive {fb['naive_ns']:.3g} ns  "
                  f"(比 {fb['naive_ns']/m_ns:.2f})")
            print("  一致(~1)なら確定。ズレるなら flyback/多重line の扱いを meta 優先で。")
    else:
        print(err)
        raw = feedback_dwell_via_raw(scnnr) if os.path.exists(scnnr) else None
        print("raw .scnnr.dat:", raw)
        print("  -> ivwib 環境で実行すると cycle/sample から dwell が出る。")

    # レシピ
    recipe(als_dwell, als_n_samp or CONDQC_PIXELS)


if __name__ == "__main__":
    main()
