import asyncio
from collections import deque
import time

from matplotlib import pyplot as plt
from matplotlib.widgets import TextBox
import numpy as np

from scipy.signal import find_peaks

from diagnostics import DiagnosticsMonitor


class ModulationAnalyzer:
    def __init__(self, snapshot_fraction, modulation_frequency):
        self.timestamp_queue = deque(maxlen=int(1 / snapshot_fraction))

        self.modulation_frequency = modulation_frequency
        self.scanning_interval = snapshot_fraction / modulation_frequency
        self.diagnostics_monitor = DiagnosticsMonitor(self)

    def update_samples(self, u_congwin, u_in_flight, delta_t):
        if len(self.timestamp_queue) > 0:
            print(len(self.timestamp_queue))
            print(
                -self.timestamp_queue[0][0]
                + self.timestamp_queue[len(self.timestamp_queue) - 1][0]
            )
        self.timestamp_queue.append(
            (delta_t, u_congwin, u_in_flight)
        )  # append new timestamp

        timestamps, congwin, in_flight = zip(*self.timestamp_queue)  # unpack
        if len(timestamps) > 1:
            fft = np.fft.fft(in_flight - np.mean(in_flight))
            freqs = np.fft.fftfreq(
                len(in_flight - np.mean(in_flight)),
                d=(timestamps[1] - timestamps[0]),
            )  # fft frequency distribution

        self.diagnostics_monitor.diagnostics_queue.append(
            (delta_t, u_congwin, u_in_flight)
        )
        print(len(self.diagnostics_monitor.diagnostics_queue))

    def last_maximum(self):
        # hard coded sample size, last n entries of self.timestamp_queue[2], based on self.modulation_frequency@1Hz, self.scanning_granurality@0.001
        # includes approx. 1 period
        # replace with dedicated logic to determine best sample size
        # shouldn't be called every cycle
        # sample_size =
        return
