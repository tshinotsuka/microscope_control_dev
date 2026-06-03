"""
analysis_postprocess.py  –  取得後の解析スクリプト（Python）
=============================================================
BehaviorAcquisition.m が保存した HDF5 ファイルを読み込んで解析する。
実験中は MATLAB が DAQ を占有するため、Python はここだけで使う。

依存: pip install numpy h5py scipy matplotlib
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
import numpy as np
import h5py
import scipy.signal as sig
import matplotlib.pyplot as plt

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ══════════════════════════════════════════════════════════
#  読み込み
# ══════════════════════════════════════════════════════════

class BehaviorSession:
    """
    BehaviorAcquisition.m が保存した HDF5 セッションを読み込む。

    使い方::

        sess = BehaviorSession("data/20250513_120000")
        print(sess)

        vel = sess["velocity"]          # チャンネルデータ取得
        fi  = sess.frame_sample_index   # フレームのサンプルインデックス
        ft  = sess.frame_time_s         # フレームの時刻 [s]

        # フレームごとの速度を切り出し
        per_frame = sess.align_to_frames("velocity", pre=0, post=int(sess.fs/30))
    """

    def __init__(self, session_dir: str | Path):
        self.session_dir = Path(session_dir)
        self._load()

    def _load(self):
        h5_path = self.session_dir / "behavior.h5"
        if not h5_path.exists():
            raise FileNotFoundError(f"HDF5 が見つかりません: {h5_path}")

        with h5py.File(h5_path, "r") as f:
            self.fs      = float(f.attrs["sample_rate"])
            self.session = str(f.attrs.get("session_name", ""))
            self.n_ch    = int(f.attrs.get("n_channels", 0))

            self.time    = f["time"][:].astype(np.float64)
            self.n_samp  = len(self.time)

            # アナログデータ
            self.channels: dict[str, np.ndarray] = {}
            for name in f["analog"]:
                self.channels[name] = f["analog"][name][:].astype(np.float32)

            # フレームログ
            if "frame_log" in f:
                self.frame_number       = f["frame_log/frame_number"][:].astype(np.int32)
                self.frame_sample_index = f["frame_log/sample_index"][:].astype(np.int64)
                self.frame_time_s       = f["frame_log/time_s"][:].astype(np.float64)
                self.n_frames           = int(f["frame_log"].attrs.get("n_frames", len(self.frame_number)))
            else:
                self.frame_number = self.frame_sample_index = self.frame_time_s = np.array([])
                self.n_frames = 0

        # config.json
        cfg_path = self.session_dir / "config.json"
        self.config = json.load(open(cfg_path)) if cfg_path.exists() else {}

        log.info(f"読み込み完了: {h5_path.name}  "
                 f"Fs={self.fs} Hz  {self.n_samp:,} smp  {self.n_frames} frames")

    def __getitem__(self, channel_name: str) -> np.ndarray:
        return self.channels[channel_name]

    def __repr__(self):
        dur = self.n_samp / self.fs if self.fs > 0 else 0
        return (f"BehaviorSession('{self.session}', "
                f"Fs={self.fs} Hz, {dur:.1f} s, "
                f"{len(self.channels)} ch, {self.n_frames} frames)")

    @property
    def channel_names(self) -> list[str]:
        return list(self.channels.keys())

    # ── フレームアライメント ─────────────────────────────────────────
    def align_to_frames(
        self,
        channel: str,
        pre: int = 0,
        post: int = 100,
        agg: str = "none",
    ) -> np.ndarray:
        """
        フレームトリガーに揃えてスニペット行列を返す。

        Returns
        -------
        ndarray (n_frames, pre+post)  または agg="mean" のとき (pre+post,)
        """
        data = self[channel]
        fi   = self.frame_sample_index
        win  = pre + post
        n    = len(data)

        snippets = [data[idx - pre: idx + post]
                    for idx in fi if (idx - pre) >= 0 and (idx + post) <= n]
        if not snippets:
            return np.empty((0, win))

        mat = np.stack(snippets, axis=0)
        if agg == "mean":   return mat.mean(0)
        if agg == "median": return np.median(mat, 0)
        return mat

    # ── イベント検出 ──────────────────────────────────────────────────
    def detect_events(
        self,
        channel: str,
        threshold: float,
        direction: str = "rising",
        min_gap: int = 50,
    ) -> np.ndarray:
        """閾値交差のサンプルインデックスを返す"""
        data  = self[channel]
        above = (data > threshold).astype(np.int8)
        diff  = np.diff(above, prepend=above[0])
        d_map = {"rising": 1, "falling": -1, "both": 0}
        v = d_map.get(direction, 1)
        edges = np.flatnonzero(diff == v) if v != 0 else np.flatnonzero(diff != 0)
        if len(edges) < 2:
            return edges
        keep      = np.empty(len(edges), dtype=bool)
        keep[0]   = True
        keep[1:]  = np.diff(edges) >= min_gap
        return edges[keep]

    # ── スニペット切り出し ────────────────────────────────────────────
    def extract_snippets(
        self,
        event_idx: np.ndarray,
        pre_s: float = 1.0,
        post_s: float = 2.0,
        channels: list[str] | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Returns
        -------
        snippets : (n_events, n_channels, n_win)
        t_win    : (n_win,)  [s]
        """
        pre  = int(pre_s  * self.fs)
        post = int(post_s * self.fs)
        win  = pre + post
        ch_list = channels or self.channel_names
        n    = self.n_samp

        valid = event_idx[(event_idx >= pre) & (event_idx + post <= n)]
        out = np.zeros((len(valid), len(ch_list), win), dtype=np.float32)
        for k, idx in enumerate(valid):
            for j, c in enumerate(ch_list):
                out[k, j] = self[c][idx - pre: idx + post]

        t_win = (np.arange(win) - pre) / self.fs
        return out, t_win

    # ── フィルタリング ────────────────────────────────────────────────
    def lowpass(self, channel: str, cutoff_hz: float, order: int = 4) -> np.ndarray:
        nyq = self.fs / 2
        sos = sig.butter(order, cutoff_hz / nyq, btype="low", output="sos")
        return sig.sosfiltfilt(sos, self[channel]).astype(np.float32)

    def bandpass(self, channel: str, low_hz: float, high_hz: float, order: int = 4) -> np.ndarray:
        nyq = self.fs / 2
        sos = sig.butter(order, [low_hz / nyq, high_hz / nyq], btype="band", output="sos")
        return sig.sosfiltfilt(sos, self[channel]).astype(np.float32)

    # ── 簡易プロット ─────────────────────────────────────────────────
    def plot(
        self,
        channels: list[str] | None = None,
        t_start: float = 0.0,
        t_end: float | None = None,
        show_frames: bool = True,
        figsize: tuple = (14, 3),
    ):
        """
        全チャンネルを縦に並べてプロットする。

        Parameters
        ----------
        t_start / t_end : 表示範囲 [s]
        show_frames     : フレームトリガー位置を縦線で表示
        """
        ch_list = channels or self.channel_names
        t_end   = t_end or self.time[-1]
        mask    = (self.time >= t_start) & (self.time <= t_end)
        t_plot  = self.time[mask]

        n = len(ch_list)
        fig, axes = plt.subplots(n, 1, figsize=(figsize[0], figsize[1] * n),
                                 sharex=True)
        if n == 1:
            axes = [axes]

        colors = plt.cm.tab10.colors
        for i, (ax, name) in enumerate(zip(axes, ch_list)):
            ax.plot(t_plot, self[name][mask], lw=0.7,
                    color=colors[i % len(colors)], label=name)
            if show_frames and len(self.frame_time_s):
                ft_vis = self.frame_time_s[
                    (self.frame_time_s >= t_start) & (self.frame_time_s <= t_end)
                ]
                ax.vlines(ft_vis, *ax.get_ylim(), color="gray",
                          lw=0.4, alpha=0.5, label="_nolegend_")
            ax.set_ylabel(name, fontsize=8)
            ax.grid(True, lw=0.3, alpha=0.5)

        axes[-1].set_xlabel("Time [s]")
        axes[0].set_title(f"{self.session}  ({self.n_frames} frames)", fontsize=10)
        fig.tight_layout()
        return fig, axes


# ══════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python analysis_postprocess.py <session_dir> [channel] [t_start] [t_end]")
        sys.exit(1)

    sess = BehaviorSession(sys.argv[1])
    print(sess)

    ch     = sys.argv[2] if len(sys.argv) > 2 else sess.channel_names[0]
    t0     = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    t1     = float(sys.argv[4]) if len(sys.argv) > 4 else min(30.0, sess.time[-1])

    fig, _ = sess.plot(t_start=t0, t_end=t1)
    plt.show()
