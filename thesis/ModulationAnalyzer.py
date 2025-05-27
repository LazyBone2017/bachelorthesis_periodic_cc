import asyncio
from collections import deque
import os
import time

from matplotlib import pyplot as plt
from matplotlib.mlab import detrend
from matplotlib.widgets import TextBox
import numpy as np

import scipy
from scipy.signal import find_peaks

from diagnostics import DiagnosticsMonitor


class ModulationAnalyzer:
    def __init__(self, modulation_frequency):
        # self.timestamp_queue.append(([], [], []))
        self.modulation_frequency = modulation_frequency
        self.timestamp_queue = deque(maxlen=self.calculate_queue_size())

        self.diagnostics_monitor = DiagnosticsMonitor()
        self.last_peak_freq = None

    # pushes data into the queue

    def calculate_queue_size(self):
        return int(
            (3 / self.modulation_frequency) * (1 / 0.1)
        )  # given 0.1 is the timestamp interval

    def update_samples(self, u_congwin, u_in_flight, delta_t):
        self.timestamp_queue.append((u_congwin, u_in_flight, delta_t))
        fft = None
        peak_freq = None
        if len(self.timestamp_queue) > 1:
            congwin, in_flight, timestamps = zip(*self.timestamp_queue)

            timestamps_uniform = np.arange(timestamps[0], timestamps[-1], 0.1)
            interpolated_fn = scipy.interpolate.interp1d(
                timestamps, in_flight, kind="linear", fill_value="extrapolate"
            )
            in_flight_uniform = interpolated_fn(timestamps_uniform)

            signal = in_flight_uniform - np.mean(in_flight_uniform)
            signal = detrend(
                signal, "linear", axis=0
            )  # important, has to be connected to linear increase mode

            window = np.hanning(len(signal))
            signal_windowed = signal * window
            fft = np.fft.rfft(signal_windowed)
            freqs = np.fft.rfftfreq(len(signal_windowed), d=0.1)
            fft_magnitude = np.abs(fft)

            peak_index = np.argmax(fft_magnitude)
            peak_freq = freqs[peak_index]
            alpha = 0.2  # smoothing factor
            if self.last_peak_freq is not None:
                peak_freq = alpha * peak_freq + (1 - alpha) * self.last_peak_freq
            self.last_peak_freq = peak_freq

        self.diagnostics_monitor.queue.append(
            (delta_t, u_congwin, u_in_flight, self.last_peak_freq)
        )

        self.diagnostics_monitor.output_queue.append(
            (delta_t, u_congwin, u_in_flight, self.last_peak_freq)
        )

    def last_maximum(self):
        # hard coded sample size, last n entries of self.timestamp_queue[2], based on self.modulation_frequency@1Hz, self.scanning_granurality@0.001
        # includes approx. 1 period
        # replace with dedicated logic to determine best sample size
        # shouldn't be called every cycle
        # sample_size =
        return
