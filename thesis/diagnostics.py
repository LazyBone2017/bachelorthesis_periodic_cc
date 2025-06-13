import asyncio
from collections import deque
import csv
import os
import threading
import time
from matplotlib import pyplot as plt
from matplotlib.mlab import detrend
from matplotlib.widgets import TextBox
import matplotlib
from nicegui import ui
import numpy as np
import scipy


def save_to_csv(filename, data):
    print("CWD:", os.getcwd())
    with open(filename + ".csv", mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(data)
    print("WRITTEN to file")


class DiagnosticsMonitor:
    def __init__(self):
        self.queue = deque(maxlen=100)
        self.init_ui()
        # matplotlib.interactive(True)
        self.counter = 0
        self.output_queue = deque()
        self.UI_enabled = True

    def piecewise_constant_interpolation(self, timestamps, values, uniform_t):
        result = np.zeros_like(uniform_t)
        idx = 0
        for i, t in enumerate(uniform_t):
            # Move idx forward while next timestamp <= t
            while idx + 1 < len(timestamps) and timestamps[idx + 1] <= t:
                idx += 1
            result[i] = values[idx]
        return result

    def init_ui(self):
        # amplitude chart, frequency chart
        fig, (self.ax_time, self.ax_rtt, self.ax_freq_rolling, self.ax_freq) = (
            plt.subplots(1, 4, figsize=(10, 4))
        )  # 1 row, 2 columns
        """self.timestamp_queue.append(
            DiagnosticsMonitor(
                time.monotonic(), self.bytes_in_flight, self.congestion_window
            )
        )
        timestamps, in_flight, congwin = zip(*self.timestamp_queue)
        """
        # amplitude graph
        (self.line_amplitude_in_flight,) = self.ax_time.plot(
            [], [], "r-"
        )  # Red line for in_flight

        (self.line_amplitude_congwin,) = self.ax_time.plot(
            [], [], "g-"
        )  # green line for congwin

        (self.line_amplitude_congwin_detrended,) = self.ax_time.plot(
            [], [], "b-"
        )  # green line for congwin
        (self.line_amplitude_trend,) = self.ax_time.plot(
            [], [], "o-"
        )  # green line for congwin

        # frequency graph
        (self.line_rtt,) = self.ax_rtt.plot([], [], "b-")

        (self.line_freq,) = self.ax_freq.plot([], [], "b-")

        (self.line_freq_rolling,) = self.ax_freq_rolling.plot([], [], "o-")

        # self.ax_time.set_ylim(90000, 110000)

        plt.ion()
        asyncio.create_task(self.update_ui())

    async def update_ui(self):
        while True:
            if len(self.queue) > 0:
                if len(self.output_queue) == 700:
                    save_to_csv("../data_out/data", self.output_queue)
                if len(self.output_queue) % 100 == 0:
                    print("Output queue len: " + str(len(self.output_queue)))
                if self.UI_enabled:

                    (
                        timestamps,
                        congwin,
                        in_flight,
                        peak_freq,
                        latest_rtt,
                        magnitudes,
                        freqs,
                    ) = zip(*self.queue)
                    self.line_amplitude_in_flight.set_xdata(timestamps)  # set data
                    self.line_amplitude_in_flight.set_ydata(in_flight)  # set data

                    self.line_amplitude_congwin.set_xdata(timestamps)  # set data
                    self.line_amplitude_congwin.set_ydata(congwin)  # set data

                    self.ax_time.relim()
                    self.ax_time.autoscale_view()

                    if len(timestamps) > 1 and False:
                        timestamps_uniform = np.arange(
                            timestamps[0], timestamps[-1], 0.1
                        )

                        interp_values = self.piecewise_constant_interpolation(
                            timestamps, in_flight, timestamps_uniform
                        )

                        in_flight_uniform = interp_values

                        signal = in_flight_uniform - np.mean(in_flight_uniform)
                        signal = detrend(
                            signal, "linear", axis=0
                        )  # important, has to be connected to linear increase mode

                        window = np.hanning(len(signal))
                        signal_windowed = signal * window
                        fft = np.fft.rfft(signal_windowed)
                        freqs = np.fft.rfftfreq(len(signal_windowed), d=0.1)
                        # maybe replace with normal conditional
                        self.line_freq.set_xdata(freqs[freqs > 0])
                        self.line_freq.set_ydata(np.abs(fft[freqs > 0]))
                        self.ax_freq.relim()
                        # self.ax_freq.set_xlim(left=0)
                        self.ax_freq.autoscale_view()

                    """strongest_indices = np.argsort(magnitudes)[-5:]

                    # Sort them by strength descending
                    strongest_indices = strongest_indices[
                        np.argsort(magnitudes[strongest_indices])[::-1]
                    ]

                    # Extract frequencies and their magnitudes
                    strongest_freqs = freqs[strongest_indices]
                    strongest_mags = magnitudes[strongest_indices]
                    """

                    print(freqs[-1])
                    if freqs[-1] is not None:

                        freqs = np.array(freqs[-1])
                        print("-----------")
                        print(freqs)
                        print("-----------")

                        self.line_freq.set_xdata(freqs[freqs > 0])
                        self.line_freq.set_ydata(magnitudes)
                        self.ax_freq.relim()
                        # self.ax_freq.set_xlim(left=0)
                        self.ax_freq.autoscale_view()

                    self.line_freq_rolling.set_xdata(timestamps)
                    self.line_freq_rolling.set_ydata(peak_freq)
                    self.ax_freq_rolling.relim()
                    self.ax_freq_rolling.autoscale_view()

                    self.line_rtt.set_xdata(timestamps)
                    self.line_rtt.set_ydata(latest_rtt)
                    self.ax_rtt.relim()
                    self.ax_rtt.autoscale_view()

                    plt.show()
                    plt.pause(0.01)
            await asyncio.sleep(0.01)
