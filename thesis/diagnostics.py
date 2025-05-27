import asyncio
from collections import deque
import csv
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

    def init_ui(self):
        # amplitude chart, frequency chart
        fig, (self.ax_time, self.ax_freq, self.ax_freq_rolling) = plt.subplots(
            1, 3, figsize=(10, 4)
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
        (self.line_freq,) = self.ax_freq.plot([], [], "b-")

        (self.line_freq_rolling,) = self.ax_freq_rolling.plot([], [], "o-")

        # self.ax_time.set_ylim(90000, 110000)

        plt.ion()
        asyncio.create_task(self.update_ui())

    async def update_ui(self):
        while True:
            if len(self.queue) > 0:
                if len(self.output_queue) == 500:
                    save_to_csv("data", self.output_queue)
                if len(self.output_queue) % 100 == 0:
                    print("Output queue len: " + str(len(self.output_queue)))
                if self.UI_enabled:

                    timestamps, congwin, in_flight, peak_freq = zip(*self.queue)
                    self.line_amplitude_in_flight.set_xdata(timestamps)  # set data
                    self.line_amplitude_in_flight.set_ydata(in_flight)  # set data

                    self.line_amplitude_congwin.set_xdata(timestamps)  # set data
                    self.line_amplitude_congwin.set_ydata(congwin)  # set data

                    self.ax_time.relim()
                    self.ax_time.autoscale_view()
                    """
                    if len(timestamps) > 1:
                        timestamps_uniform = np.arange(timestamps[0], timestamps[-1], 0.1)
                        interpolated_fn = scipy.interpolate.interp1d(
                            timestamps, congwin, kind="linear", fill_value="extrapolate"
                        )
                        congwin_uniform = interpolated_fn(timestamps_uniform)
                        signal = congwin_uniform  # - np.mean(congwin_uniform)
                        fft = np.fft.fft(signal)
                        fft_magnitude = np.abs(fft)
                        freqs = np.fft.fftfreq(
                            len(congwin_uniform - np.mean(congwin_uniform)),
                            d=0.1,
                        )  # fft frequency distribution

                        # maybe replace with normal conditional
                        self.line_freq.set_xdata(freqs[freqs > 0])
                        self.line_freq.set_ydata(np.abs(fft[freqs > 0]))
                        self.ax_freq.relim()
                        # self.ax_freq.set_xlim(left=0)
                        self.ax_freq.autoscale_view()"""

                    self.line_freq_rolling.set_xdata(timestamps)
                    self.line_freq_rolling.set_ydata(peak_freq)
                    self.ax_freq_rolling.relim()
                    self.ax_freq_rolling.autoscale_view()

                    plt.show()
                    plt.pause(0.01)
            await asyncio.sleep(0.01)
