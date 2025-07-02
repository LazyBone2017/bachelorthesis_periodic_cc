from collections import deque

from matplotlib.mlab import detrend
import numpy as np
import scipy


# unit holds a single version of all processing applied _acks_in_process, saving intermediary states in dedicated fields


class AnalyzerUnit:
    def __init__(self, sampling_rate, modulation_frequency):
        self._sampling_rate = sampling_rate
        self._modulation_frequency = modulation_frequency
        self.input_queue = deque(maxlen=int(sampling_rate / modulation_frequency * 5))
        self._acks_in_process = []
        self._delta_t = []
        self._raw_acks = []
        self._congwin = []

        self._delta_t_uniform = []
        self._filtered_acks = []
        self._interpolated_acks = []
        self._detrended_acks = []
        self._windowed_acks = []
        self._padded_acks = []
        self._fft_magnitudes = []
        self._fft_freqs = np.array([])
        self._rtt_estimate = 0
        self._base_to_second_harmonic_ratio = deque(maxlen=self.input_queue.maxlen)
        self._ratio_averaged = deque([0], maxlen=self.input_queue.maxlen)

    def gen_uniform_delta_t(self):
        self._delta_t_uniform = np.arange(
            self._delta_t[0], self._delta_t[-1], 1 / self._sampling_rate
        )

    def apply_filter(self, window):
        if len(self._acks_in_process) <= 4:
            self._filtered_acks = self._acks_in_process
        else:
            self._filtered_acks = scipy.signal.savgol_filter(
                self._acks_in_process, window_length=window, polyorder=window - 1
            )
        return self._filtered_acks

    def apply_interpolation(self):
        if len(self._acks_in_process) == 0:
            return
        self._interpolated_acks = np.interp(
            self._delta_t_uniform, self._delta_t, self._acks_in_process
        )
        return self._interpolated_acks

    def apply_detrending(self):
        if len(self._acks_in_process) == 0:
            return self._acks_in_process
        self._detrended_acks = detrend(self._acks_in_process, "linear", axis=0)
        return self._detrended_acks

    def apply_windowing(self):
        if len(self._acks_in_process) == 0:
            self._windowed_acks = self._acks_in_process
        window = np.hanning(len(self._acks_in_process))
        self._windowed_acks = self._acks_in_process * window
        return self._windowed_acks

    def apply_zero_padding(self, factor):
        if len(self._acks_in_process) == 0:
            self._padded_acks = self._acks_in_process
        self._padded_acks = np.pad(
            self._acks_in_process, (0, len(self._acks_in_process) * factor), "constant"
        )
        return self._padded_acks

    def generate_fft(self):
        if len(self._acks_in_process) == 0:
            return
        self._fft_magnitudes = np.abs(np.fft.rfft(self._acks_in_process))
        self._fft_freqs = np.fft.rfftfreq(
            len(self._acks_in_process), d=1 / self._sampling_rate
        )

    def generate_base_to_second_harmonic_ratio(self):
        if len(self._fft_freqs) == 0:
            self._base_to_second_harmonic_ratio.append(0)
            return
        base_magnitude = self._fft_magnitudes[
            np.argmin(np.abs(self._fft_freqs - self._modulation_frequency))
        ]
        second_harmonic_magnitude = self._fft_magnitudes[
            np.argmin(np.abs(self._fft_freqs - self._modulation_frequency * 2))
        ]
        if base_magnitude == 0:
            self._base_to_second_harmonic_ratio.append(0)
            return

        self._base_to_second_harmonic_ratio.append(
            second_harmonic_magnitude / base_magnitude
        )
        self._ratio_averaged.append(
            sum(list(self._base_to_second_harmonic_ratio))
            / len(self._base_to_second_harmonic_ratio)
        )

    def update_processing(self):
        if len(self.input_queue) == 0:
            return
        self._delta_t, self._congwin, self._raw_acks, latest_rtt = zip(
            *self.input_queue
        )
        self._acks_in_process = self._raw_acks

        self.gen_uniform_delta_t()

        self._acks_in_process = self.apply_filter(window=4)
        self._acks_in_process = self.apply_interpolation()
        self._acks_in_process = self.apply_detrending()
        self._acks_in_process = self.apply_windowing()
        self._acks_in_process = self.apply_zero_padding(factor=4)

        self.generate_fft()
        self.generate_base_to_second_harmonic_ratio()

    # TODO average this in a probing manner for later
    def update_rtt(self, last_rtt):
        self._rtt_estimate = last_rtt
