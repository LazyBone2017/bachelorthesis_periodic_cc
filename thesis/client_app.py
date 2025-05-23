import asyncio
import csv
import threading

import nicegui

from QuicClient import QuicClient
from aioquic.quic.congestion.periodic import LOG
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import make_splrep, splev
from nicegui import ui

from data_provider import provider

label = None


def handle_ui():
    global label
    label = ui.label("Ts")
    nicegui.ui.run()


def save_to_csv(filename, data, fieldnames):
    with open(filename, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(data)


async def main():
    send_data_queue = asyncio.Queue()

    # Start the client and provider tasks
    client = QuicClient("localhost", 4433, send_data_queue)

    provider_task = asyncio.create_task(
        provider(send_data_queue, data_rate=1, iterations=10)
    )
    # client_task = asyncio.create_task(client.run(plot_graph))
    thread = threading.Thread(
        target=client.run(on_connection_close_callback=plot_graph()), daemon=True
    )
    await thread.run()
    # Wait for both tasks to finish
    await asyncio.gather(provider_task)


def plot_graph():
    return

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
    in_flight = congwin
    in_flight_mean_reduced = in_flight - np.mean(in_flight)

    time = np.linspace(0, 10, 1000)
    signal = np.sin(2 * np.pi * 1 * time) + 0.5  # 1Hz signal + DC offset

    dt = np.diff(timestamps)
    print("Mean interval:", np.mean(dt))
    print("Standard deviation:", np.std(dt))

    signal_demeaned = signal - np.mean(signal)

    # 2. Perform FFT
    fft_result = np.fft.fft(signal_demeaned)

    # 3. Get frequencies
    freqs = np.fft.fftfreq(len(signal_demeaned), d=(time[1] - time[0]))

    # 4. Plot positive frequencies
    mask = freqs > 0
    plt.plot(freqs[mask], np.abs(fft_result)[mask])
    plt.title("Frequency domain after mean removal")
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Amplitude")
    plt.xlim(0, 5)  # optional: zoom into 0-5 Hz
    plt.grid()
    plt.show()

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


if __name__ in {"__main__", "__mp_main__"}:
    handle_ui()
    asyncio.run(main())
