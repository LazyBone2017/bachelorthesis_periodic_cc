import pandas as pd
import matplotlib.pyplot as plt
import sys
import os


def plot_metrics(csv_file, metrics):
    # Load CSV
    df = pd.read_csv(csv_file)

    # Rename delta_t → time_s (explicitly: absolute time since start)
    if "delta_t" in df.columns:
        df = df.rename(columns={"delta_t": "time_s"})

    # Derive extra columns if needed
    if "acked_byte" in df.columns and "time_s" in df.columns:
        # goodput: acked payload delivered per interval
        df["goodput"] = (
            (df["acked_byte"] * 8) / df["time_s"].diff().fillna(df["time_s"]) / 1e6
        )
    if "sent_byte" in df.columns and "time_s" in df.columns:
        df["throughput"] = (
            (df["sent_byte"] * 8) / df["time_s"].diff().fillna(df["time_s"]) / 1e6
        )

    # Plot all selected metrics in one figure
    plt.figure(figsize=(7, 5))

    for metric in metrics:
        if metric not in df.columns:
            print(f"Warning: metric '{metric}' not in dataframe, skipping.")
            continue
        plt.plot(df["time_s"], df[metric], label=metric.capitalize())

    plt.xlabel("Time (s)")
    plt.ylabel("Value")
    plt.title("Metrics over Time")
    plt.legend()
    plt.tight_layout()

    # Save combined plot
    metrics_str = "_".join(metrics)
    filename = f"{csv_file[0:-4]}_{metrics_str}.pdf"
    plt.savefig(filename)
    plt.close()
    print(f"Written {filename}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python plot_metrics.py <csv_file> <metric1> [metric2 ...]")
        sys.exit(1)

    csv_file = sys.argv[1]
    metrics = sys.argv[2:]
    plot_metrics(csv_file, metrics)
