#!/usr/bin/env python3
import os
import sys
import glob
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

# Usage:
#   python avg_cwndbase_plot.py BASE_PATH folder1 folder2 folder3 ...
#
# Example:
#   python avg_cwndbase_plot.py ./results jitter_0 jitter_5 jitter_10 jitter_15


def load_runs(folder_path):
    """Load all *_raw.csv files from the given folder into a list of DataFrames."""
    files = sorted(glob.glob(os.path.join(folder_path, "*_raw.csv")))
    runs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            if {"delta_t", "cwnd_base"}.issubset(df.columns):
                runs.append(df[["delta_t", "cwnd_base"]].copy())
                print(f"Loaded {f}")
        except Exception as e:
            print(f"[WARN] Skipping {f}: {e}")
    return runs


def interpolate_to_longest(runs, metric="cwnd_base"):
    """Interpolate all runs to the time axis of the longest run."""
    if not runs:
        return None, None

    # Find run with the largest max(delta_t)
    longest_run = max(runs, key=lambda r: r["delta_t"].max())
    base_t = longest_run["delta_t"].to_numpy()

    # Interpolate all runs onto base_t
    interp_data = []
    for r in runs:
        s = pd.Series(r[metric].values, index=r["delta_t"].values)
        s_interp = s.reindex(base_t).interpolate(method="linear").to_numpy()
        interp_data.append(s_interp)

    mat = np.vstack(interp_data)
    mean = np.nanmean(mat, axis=0)
    std = np.nanstd(mat, axis=0)
    return base_t, (mean, std)


def main(base_path, folders):
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    for folder in folders:
        path = os.path.join(base_path, folder)
        runs = load_runs(path)
        if not runs:
            print(f"[WARN] No valid runs in {path}")
            continue

        t, (mean, std) = interpolate_to_longest(runs, "cwnd_base")
        label = folder.replace("_", ".")
        ax.plot(t, mean, lw=2.2, label=label)
        ax.fill_between(t, mean - std, mean + std, alpha=0.2)

    ax.set_title(None)
    ax.grid(True, alpha=0.2)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.set_ylim(bottom=0)
    plt.tick_params(axis="both", which="major", labelsize=12)
    plt.xlabel("t [s]", fontsize=12)
    plt.ylabel("cwnd$_{base}$ [bytes]", fontsize=12)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    plt.tight_layout()
    plt.savefig("avg_cwndbase_vs_time_wide.png", dpi=300, bbox_inches="tight")
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python avg_cwndbase_plot.py BASE_PATH folder1 folder2 ...")
        sys.exit(1)
    base_path = sys.argv[1]
    folders = sys.argv[2:]
    main(base_path, folders)
