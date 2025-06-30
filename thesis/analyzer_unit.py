from collections import deque

from matplotlib.mlab import detrend
import numpy as np
import scipy

#TODO encapsulate
class AnalyzerUnit:
    def ___init___(self, sampling_rate):
        self.sampling_rate = sampling_rate
        self.input_queue = deque()

        self.acks_in_process = []

        self.delta_t_uniform = []
        self.filtered_acks = []
        self.interpolated_acks = []
        self.detrended_acks = []
        self.windowed_acks = []
        self.padded_acks = []
        self.fft_magnitudes = []
        self.fft_freqs = []

    def gen_uniform_delta_t(self, delta_t):
        self.delta_t_uniform = np.arange(
            delta_t[0], delta_t[-1], 1 / self.sampling_rate
        )

    def apply_filter(self, window):
        if len(self.acks_in_process) <= 4:
            return self.acks_in_process
        else:
            self.filtered_acks = scipy.signal.savgol_filter(
                self.acks_in_process, window_length=window, polyorder=window - 1
            )
            return self.filtered_acks

    def apply_interpolation(self, delta_t):
        self.interpolated_acks = np.interp(
            self.delta_t_uniform, delta_t, self.acks_in_process
        )
        return self.interpolated_acks

    def apply_detrending(self):
        self.detrended_acks = detrend(self.acks_in_process, "linear", axis=0)
        return self.detrended_acks

    def apply_windowing(self):
        window = np.hanning(len(self.acks_in_process))
        self.windowed_acks = self.acks_in_process * window
        return self.windowed_acks

    def apply_zero_padding(self, factor):
        self.padded_acks = np.pad(
            self.acks_in_process, (0, len(self.acks_in_process) * factor), "constant"
        )

    def generate_fft(self):
        self.fft_magnitudes = np.abs(np.fft.rfft(self.acks_in_process))
        self.fft_freqs = np.fft.rfftfreq(
            len(self.acks_in_process), d=1 / self.sampling_rate
        )

    def update(self):
        if len(self.input_queue) == 0:
            return
        delta_t, congwin, self.acks_in_process, latest_rtt = zip(*self.input_queue)

        self.gen_uniform_delta_t(delta_t)

        self.acks_in_process = self.apply_filter(window=4)
        self.acks_in_process = self.apply_interpolation(delta_t)
        self.acks_in_process = self.apply_detrending()
        self.acks_in_process = self.apply_windowing()
        self.acks_in_process = self.apply_zero_padding(factor=4)

        self.generate_fft()
