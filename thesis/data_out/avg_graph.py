#!/usr/bin/env python3
import os, sys
from matplotlib.rcsetup import cycler
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

okabe_ito = [
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # bluish green
    "#F0E442",  # yellow
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#CC79A7",  # reddish purple
    "#000000",  # black (optional)
]

# Set as global default
plt.rcParams["axes.prop_cycle"] = cycler(color=okabe_ito)

# Usage: python metrics_from_folder.py ./pulse/baseline


def compute_metrics_one(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-interval goodput, RTT, and loss rate."""
    df = df.sort_values("delta_t").reset_index(drop=True)

    t = df["delta_t"].astype(float)
    dt = t.diff()
    mask = dt > 0
    t = t[mask]
    dt = dt[mask]

    # --- Goodput ---
    if "acked_byte" in df.columns:
        ab = df["acked_byte"].astype(float)
        bytes_interval = ab.clip(lower=0).fillna(0)[mask]
        goodput = (bytes_interval * 8.0) / dt / 1e6  # Mbit/s
    else:
        goodput = np.full_like(t, np.nan)

    # --- RTT ---
    if "rtt" in df.columns:
        rtt = df["rtt"].astype(float)[mask] * 1000
    else:
        rtt = np.full_like(t, np.nan)

    # --- Loss rate ---
    if "lost_byte" in df.columns:
        lb = df["lost_byte"].astype(float)
        sb = df["sent_byte"].astype(float)
        lost_interval = lb.clip(lower=0).fillna(0)[mask]
        bytes_interval = sb.clip(lower=0).fillna(0)[mask]
        loss_pct = np.where(
            bytes_interval > 0, (lost_interval / bytes_interval) * 100, 0.0
        )
    else:
        loss_pct = np.full_like(t, np.nan)

    return pd.DataFrame(
        {"t": t.values, "goodput": goodput, "rtt": rtt, "loss_rate": loss_pct}
    )


def load_runs(folder: str):
    runs = []
    for f in sorted(os.listdir(folder)):
        if not f.endswith("_raw.csv"):
            continue
        fpath = os.path.join(folder, f)
        try:
            df = pd.read_csv(fpath)
            if "delta_t" in df.columns:
                metrics = compute_metrics_one(df)
                if not metrics.empty:
                    runs.append(metrics)
                print(f"[OK] {f}")
            else:
                print(f"[WARN] Missing 'delta_t' in {f}")
        except Exception as e:
            print(f"[ERR] {fpath}: {e}")
    return runs


def plot_metric(folder: str, runs, metric: str, ylabel: str):
    y_limits = {
        "goodput": (0, 11),  # example: 0–50 Mbit/s
        "rtt": (0, 300),  # example: 0–0.3 s
        "loss_rate": (0, 50),  # example: 0–3 %
    }
    """Plot mean ± std for a given metric across all runs."""

    # --- Replace this part ---
    # Create a common time axis that covers all runs
    all_t = np.unique(np.concatenate([r["t"].values for r in runs]))
    all_t.sort()

    # Interpolate each run onto the common time grid
    data_interp = []
    for r in runs:
        s = pd.Series(r[metric].values, index=r["t"].values)
        s_interp = s.reindex(all_t).interpolate(method="linear").to_numpy()
        data_interp.append(s_interp)

    mat = np.vstack(data_interp)
    mean = np.nanmean(mat, axis=0)
    std = np.nanstd(mat, axis=0)
    ts = all_t
    # --- End replacement ---

    """minlen = min(len(r) for r in runs)
    ts = runs[0]["t"].iloc[:minlen]
    data = [r[metric].iloc[:minlen] for r in runs]

    mat = pd.concat(data, axis=1)
    mean = mat.mean(axis=1)
    std = mat.std(axis=1)"""

    plt.figure(figsize=(6.4, 3.2))
    plt.plot(ts, mean, label=f"Mean {metric}")
    plt.fill_between(ts, mean - std, mean + std, alpha=0.2, lw=2.2)
    plt.xlabel("t [s]")
    plt.ylabel(ylabel)
    plt.grid(True, alpha=0.2)
    plt.ylim(*y_limits[metric])
    plt.tick_params(axis="both", which="major", labelsize=12)
    plt.xlabel("t [s]", fontsize=12)
    plt.ylabel(ylabel, fontsize=12)

    if metric == "loss_rate":
        plt.yscale("symlog", linthresh=2.0, base=10)
        plt.ylim(bottom=0, top=1e2)
    plt.tight_layout()

    parts = os.path.normpath(folder).split(os.sep)
    algo = parts[-2] if len(parts) >= 2 else "unknown_algo"
    testcase = parts[-1]
    out = f"{folder}/{algo}_{testcase}_{metric}_avg.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    print(f"[OK] Saved {out}")
    plt.close()


def plot_all(folder: str, metric=None):
    runs = load_runs(folder)
    if not runs:
        print("No *_raw.csv files found.")
        return

    metrics = [
        ("goodput", "Goodput [Mbit/s]"),
        ("rtt", "RTT [ms]"),
        ("loss_rate", "Loss rate [%] (symlog scale)"),
    ]
    for name, ylabel in metrics:
        if metric and name != metric:
            continue
        plot_metric(folder, runs, name, ylabel)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python metrics_from_folder.py <folder>")
        sys.exit(1)
    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print(f"Error: folder not found: {folder}")
        sys.exit(1)
    if len(sys.argv) < 3:
        plot_all(folder)
    else:
        plot_all(folder, sys.argv[2])
