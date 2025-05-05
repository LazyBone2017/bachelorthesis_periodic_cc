from collections import deque
import time

from matplotlib import pyplot as plt
from matplotlib.widgets import TextBox
import numpy as np

from scipy.signal import find_peaks


class ModulationAnalyzer:
    def __init__(self, queue_size, scanning_granularity, modulation_frequency):
        self.timestamp_queue = deque(maxlen=queue_size)
        self.shift_queue = deque(maxlen=queue_size)
        self.modulation_frequency = modulation_frequency
        self.scanning_rate = scanning_granularity / modulation_frequency
        self.init_ui()

    def init_ui(self):
        plt.ion()

        # amplitude chart, frequency chart
        fig, (self.ax_time, self.ax_freq, self.ax_shift) = plt.subplots(
            1, 3, figsize=(10, 4)
        )  # 1 row, 2 columns
        """self.timestamp_queue.append(
            (time.monotonic(), self.bytes_in_flight, self.congestion_window)
        )
        timestamps, in_flight, congwin = zip(*self.timestamp_queue)

        """  # amplitude graph
        (self.line_amplitude_in_flight,) = self.ax_time.plot(
            [], [], "r-"
        )  # Red line for in_flight

        (self.line_amplitude_congwin,) = self.ax_time.plot(
            [], [], "g-"
        )  # green line for congwin

        # frequency graph
        (self.line_freq,) = self.ax_freq.plot([], [], "b-")

        (self.line_shift,) = self.ax_shift.plot([], [], "o-")

        axbox = plt.axes([0.25, 0.05, 0.5, 0.05])
        self.textbox = TextBox(
            axbox, "Frequency:", initial=str(self.modulation_frequency)
        )
        self.textbox.on_submit(
            lambda text: setattr(self, "modulation_frequency", float(text))
        )

    def update_ui(self, u_congwin, u_in_flight):
        self.timestamp_queue.append(
            (time.monotonic(), u_congwin, u_in_flight)
        )  # append new timestamp
        timestamps, congwin, in_flight = zip(*self.timestamp_queue)  # unpack

        self.line_amplitude_in_flight.set_xdata(timestamps)  # set data
        self.line_amplitude_in_flight.set_ydata(in_flight)  # set data
        self.line_amplitude_congwin.set_xdata(timestamps)  # set data
        self.line_amplitude_congwin.set_ydata(congwin)  # set data
        self.ax_time.relim()
        self.ax_time.autoscale_view()

        fft = np.fft.fft(in_flight - np.mean(in_flight))  # create fft

        try:
            freqs = np.fft.fftfreq(
                len(in_flight - np.mean(in_flight)),
                d=(timestamps[1] - timestamps[0]),
            )  # fft frequency distribution
            self.line_freq.set_xdata(freqs)
            self.line_freq.set_ydata(np.abs(fft))
            self.ax_freq.relim()
            self.ax_freq.autoscale_view()

        except:
            print("no data")

        # TODO
        (peaks_congwin, dict) = find_peaks(congwin)
        print(peaks_congwin)

        last_congwin_peak_time = peaks_congwin[peaks_congwin[-1]]

        self.shift_queue.append((time.monotonic(), last_congwin_peak_time))

        timing, shift = zip(*self.shift_queue)
        self.line_shift.set_xdata(timing)
        self.line_shift.set_ydata(shift)
        self.ax_shift.relim()
        self.ax_shift.autoscale_view()

        plt.draw()
        plt.pause(0.05)
