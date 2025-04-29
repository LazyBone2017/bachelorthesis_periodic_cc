import asyncio
import csv

from QuicClient import QuicClient
from aioquic.quic.congestion.periodic import LOG
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import make_splrep, splev

from data_provider import provider


def save_to_csv(filename, data, fieldnames):
    with open(filename, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(data)


async def main():
    queue = asyncio.Queue()

    # Start the client and provider tasks
    client = QuicClient("localhost", 4433, queue)

    provider_task = asyncio.create_task(provider(queue, data_rate=1, iterations=50))
    client_task = asyncio.create_task(client.run(plot_graph))

    # Wait for both tasks to finish
    await asyncio.gather(provider_task, client_task)


def plot_graph():

    save_to_csv("LOG.csv", LOG, ["T", "T", "T", "T"])

    should_build_spline = False
    timestamps = np.array([v[0] for v in LOG])
    congwin = [v[1] for v in LOG]
    in_flight = np.array([v[2] for v in LOG])
    if should_build_spline:
        print("Buidling Spline...")
        spline_params = make_splrep(timestamps, in_flight, s=5)
        print("Spline built")
        timestamps_precise = np.linspace(timestamps.min(), timestamps.max(), 100)
        smoothed = splev(
            timestamps_precise,
            spline_params,
        )
    rtt = [v[3] for v in LOG]
    fig, ax = plt.subplots()

    ax.plot(timestamps, congwin, color="red")
    ax.plot(timestamps, in_flight, color="green")
    ax.plot(timestamps, rtt, color="yellow")
    if should_build_spline:
        ax.plot(timestamps_precise, smoothed, color="orange", label="Smoothed")
    ax.set_title("Sine Wave")

    ax.set_title("Graph from Points")
    ax.set_xlabel("Time(s)")
    ax.set_ylabel("n packets")

    window = tk.Tk()
    window.title("Graph Viewer")
    window.geometry("1920x1080")

    canvas = FigureCanvasTkAgg(fig, master=window)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def on_closing():
        window.destroy()
        window.quit()

    window.protocol("WM_DELETE_WINDOW", on_closing)

    window.mainloop()


if __name__ == "__main__":
    asyncio.run(main())
