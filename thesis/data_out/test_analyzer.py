import pandas as pd
import numpy as np
import sys
import os


def analyze(csv_file, output_prefix="analysis"):
    df = pd.read_csv(csv_file)

    results = {}

    # --- Goodput: total acked bytes / total time ---
    total_time = df.iloc[-1]["delta_t"]
    total_acked = df["acked_byte"].sum()
    goodput_bps = (total_acked / 1000000 * 8) / total_time if total_time > 0 else np.nan
    print("total acked", total_acked)
    results["goodput_mbit/s"] = goodput_bps

    # --- Throughput: total sent bytes / total time ---
    total_sent = df["sent_byte"].sum()
    throughput_bps = (
        (total_sent / 1000000 * 8) / total_time if total_time > 0 else np.nan
    )
    print("total sent", total_sent)
    results["throughput_mbit/s"] = throughput_bps

    # --- Loss ratio: lost / sent ---
    total_lost = df["lost_byte"].sum()
    results["loss_ratio"] = total_lost / total_sent if total_sent > 0 else np.nan

    # --- RTT stats ---
    if "rtt" in df.columns:
        results["rtt_avg"] = df["rtt"].mean()
        results["rtt_median"] = df["rtt"].median()
        results["rtt_std"] = df["rtt"].std()

    # Save metrics
    with open(f"{output_prefix}_metrics.txt", "w") as f:
        for k, v in results.items():
            f.write(f"{k}: {v:.4f}\n")

    print("Analysis done. Results:")
    for k, v in results.items():
        print(f"{k}: {v:.4f}")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze.py <csv_file> [output_prefix]")
        sys.exit(1)

    csv_file = sys.argv[1]
    output_prefix = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(csv_file)[0]
    analyze(csv_file, output_prefix)
