#!/usr/bin/env python
"""sweep_quality.py — ALS 掃引品質チェック（per-cycle peak-to-peak）

`.scnnr.dat`（scanner feedback）を cycle 単位に区切り、各 cycle の galvo 掃引幅
（peak-to-peak）を出して「galvo が毎 cycle 線をなぞっているか / park していないか」を
定量化する。旧 run-01_00002 は startup cycle 0–4 だけ掃引し以降 pp≈0.1 で park していた
（Optimize Waveform 未最適化 / MBF 25850）。本スクリプトはその故障モードを一発で見抜く。

判定の目安:
    - 5th percentile が線サイズ相当（noise floor ~0.1 ではない）= 全 cycle 掃いている = PASS
    - first10 だけ大きく以降が小さい = startup のみ掃引 = 旧データと同じ park 病 = FAIL

依存: numpy（必須）, matplotlib（任意・--plot 時のみ）, als_loader（同 repo src/python）

使い方:
    python sweep_quality.py <run>.meta.txt
    python sweep_quality.py <run>.meta.txt --n-cycles 5000 --plot
"""
from __future__ import annotations

import argparse
import sys
import numpy as np

try:
    import als_loader as al
except ImportError as exc:  # pragma: no cover
    sys.exit(f"als_loader を import できない（同 src/python から実行する）: {exc}")


# ---------------------------------------------------------------------------
# als_loader からの scanner feedback 取り出し（API 名は環境差を吸収）
# ---------------------------------------------------------------------------
def load_scanner(meta_path: str) -> np.ndarray:
    """meta から scanner feedback 配列を取り出す。

    als_loader の実 API 名が分からない場合に備え、よくある入口/属性名を順に試す。
    どれも当たらなければ dir() を出して終了（手で 1 行直せるように）。
    返り値は (Nsamp, nch) または (ncycle, spc, nch) のいずれか。
    """
    # 1) ローダ入口の候補（最初に呼べたものを使う）
    obj = None
    for fn_name in ("load", "read", "load_run", "read_run", "load_scanner",
                    "read_scanner", "AlsRun", "Run", "load_linescan"):
        fn = getattr(al, fn_name, None)
        if callable(fn):
            try:
                obj = fn(meta_path)
                print(f"[loader] als_loader.{fn_name}() を使用")
                break
            except Exception:  # noqa: BLE001  次の候補へ
                obj = None
    if obj is None:
        sys.exit("[loader] als_loader に呼べる入口が見つからない。"
                 f"利用可能: {[n for n in dir(al) if not n.startswith('_')]}")

    # 2) scanner feedback 属性の候補
    for attr in ("scanner", "scnnr", "feedback", "scanner_xy", "scn",
                 "scanner_feedback", "fdbk"):
        val = getattr(obj, attr, None)
        if val is None and isinstance(obj, dict):
            val = obj.get(attr)
        if val is not None:
            print(f"[loader] scanner = .{attr}")
            return np.asarray(val)

    sys.exit("[loader] scanner feedback 属性が見つからない。"
             f"obj の属性: {[n for n in dir(obj) if not n.startswith('_')]}")


# ---------------------------------------------------------------------------
# cycle 分割 + per-cycle pp
# ---------------------------------------------------------------------------
def per_cycle_pp(scn: np.ndarray, n_cycles: int) -> np.ndarray:
    """(ncycle,) の per-cycle 2D peak-to-peak を返す。"""
    scn = np.asarray(scn)

    if scn.ndim == 3:                       # 既に (ncycle, spc, nch)
        cyc = scn
    elif scn.ndim == 2:                     # (Nsamp, nch)
        spc = scn.shape[0] // n_cycles
        if spc == 0:
            sys.exit(f"[shape] Nsamp={scn.shape[0]} < n_cycles={n_cycles}。"
                     "--n-cycles を確認。")
        cyc = scn[: spc * n_cycles].reshape(n_cycles, spc, scn.shape[1])
    elif scn.ndim == 1:                     # 単一 ch を flat 格納
        spc = scn.shape[0] // n_cycles
        cyc = scn[: spc * n_cycles].reshape(n_cycles, spc, 1)
    else:
        sys.exit(f"[shape] 想定外の次元: {scn.shape}")

    print(f"[shape] scanner {scn.shape} -> cycles={cyc.shape[0]} "
          f"samples/cycle={cyc.shape[1]} ch={cyc.shape[2]}")

    pp_per_ch = np.ptp(cyc, axis=1)         # (ncycle, nch)  ※ NumPy 2.x は np.ptp
    if pp_per_ch.shape[1] >= 2:             # X,Y -> 2D 掃引幅
        return np.hypot(pp_per_ch[:, 0], pp_per_ch[:, 1])
    return pp_per_ch[:, 0]


def report(pp: np.ndarray) -> None:
    pct = np.percentile(pp, [0, 5, 25, 50, 75, 95, 100])
    print("\n=== per-cycle peak-to-peak ===")
    print("percentiles [0 5 25 50 75 95 100]:", np.round(pct, 3))
    print("first 10 cyc:", np.round(pp[:10], 3))
    print("last  10 cyc:", np.round(pp[-10:], 3))

    p05, p50 = pct[1], pct[3]
    # park 病の指標: 中央値が 5%tile より大きく乖離 = 一部だけ掃いている
    spread = (p50 / p05) if p05 > 0 else np.inf
    print(f"\nmedian/5th = {spread:.2f}  (1 に近い=全 cycle 安定して掃引)")

    if p05 >= 0.5 * p50 and p05 > 0:
        print("VERDICT: PASS  — 5th percentile も線サイズ相当。全 cycle が掃いている。")
    else:
        print("VERDICT: CHECK — 低い側の cycle が park 気味。first/last10 と "
              "--plot で startup のみ掃引でないか確認。")


def plot(pp: np.ndarray, out: str = "sweep_pp.png") -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[plot] matplotlib が無いのでスキップ")
        return
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.plot(pp, lw=0.6)
    ax.set_xlabel("cycle"); ax.set_ylabel("pp (2D)")
    ax.set_title("ALS scanner feedback per-cycle peak-to-peak")
    fig.tight_layout(); fig.savefig(out, dpi=120)
    print(f"[plot] saved -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("meta", help="ALS .meta.txt のパス")
    ap.add_argument("--n-cycles", type=int, default=5000,
                    help="cycle 数（als_inject_align の出力に合わせる。既定 5000）")
    ap.add_argument("--plot", action="store_true", help="pp vs cycle を png 保存")
    args = ap.parse_args()

    scn = load_scanner(args.meta)
    pp = per_cycle_pp(scn, args.n_cycles)
    report(pp)
    if args.plot:
        plot(pp)


if __name__ == "__main__":
    main()
