from collections import deque

from matplotlib.mlab import detrend
import numpy as np
import scipy
import scipy.signal


# unit holds a single version of all processing applied _acks_in_process, saving intermediary states in dedicated fields


class AnalyzerUnit:
    def __init__(self, sampling_rate, modulation_frequency, base_to_amplitude_ratio):
        self.base_to_amplitude_ratio = base_to_amplitude_ratio
        self._sampling_rate = sampling_rate
        self._modulation_frequency = modulation_frequency
        self.input_queue = deque(maxlen=int(sampling_rate / modulation_frequency * 3))
        self._acks_in_process = [0] * self.input_queue.maxlen
        self._delta_t = [0] * self.input_queue.maxlen
        self._raw_acks = [0] * self.input_queue.maxlen
        self._congwin = [0] * self.input_queue.maxlen
        self._ack_rate = [0] * self.input_queue.maxlen
        self._sent_bytes = [0] * self.input_queue.maxlen

        self._delta_t_uniform = [0] * self.input_queue.maxlen
        self._filtered_acks = [0] * self.input_queue.maxlen
        self._interpolated_acks = [0] * self.input_queue.maxlen
        self._detrended_acks = [0] * self.input_queue.maxlen
        self._windowed_acks = [0] * self.input_queue.maxlen
        self._padded_acks = [0] * self.input_queue.maxlen
        self._fft_magnitudes = [0] * self.input_queue.maxlen
        self._fft_freqs = np.array([])
        self._rtt_estimate = 0.1
        self._rtts = [0] * self.input_queue.maxlen
        self._base_to_second_harmonic_ratio = deque(
            [0] * self.input_queue.maxlen, maxlen=self.input_queue.maxlen
        )
        self._congwin_to_response_ratio = deque(
            [1] * self.input_queue.maxlen, maxlen=self.input_queue.maxlen
        )
        self._base_cwnd = deque(
            [0] * self.input_queue.maxlen, maxlen=self.input_queue.maxlen
        )

    def add_to_queue(self, entry):
        self.input_queue.append(entry)

    def gen_uniform_delta_t(self, midpoint_aligned):
        if midpoint_aligned:
            # print("----------------------------")
            # print("DELTA_T" + str(len(self._delta_t)))
            self._delta_t_uniform = (
                np.array(self._delta_t[:-1]) + np.array(self._delta_t[1:])
            ) / 2
            # print("DELTA_T_uniform" + str(len(self._delta_t_uniform)))
        else:
            self._delta_t_uniform = np.arange(
                self._delta_t[0], self._delta_t[-1], 1 / self._sampling_rate
            )

    def get_rtt_estimate(self):
        if len(self._rtts) != 0:
            return np.min(self._rtts)
        else:
            return 0.5  # fallback, is this good?

    def _calculate_shift_bytes(self):
        x = self.get_rtt_estimate() * 5000
        print("SHIFTED", x)
        return x

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

    def apply_differential(self):
        if len(self._acks_in_process) == 0:
            return
        acks_cumsum = np.cumsum(self._acks_in_process)
        delta_t_diff = np.diff(self._delta_t)
        acks_cum_diff = np.diff(acks_cumsum)
        self._ack_rate = (acks_cum_diff / delta_t_diff) / int(1 / 0.1)
        print("RATE" + str(len(self._ack_rate)))
        print("----------------------------")

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

    def get_base_to_second_harmonic_ratio(self):
        if len(self._base_to_second_harmonic_ratio) == 0:
            return None
        return self._base_to_second_harmonic_ratio[-1]

    """def generate_congwin_to_response_ratio(self):
        if self._congwin is None:
            self._congwin_to_response_ratio.append(0)
            return
        if len(self._congwin) == 0 or len(self._acks_in_process) == 0:
            print("RE")
            return

        # get congin peak and valley delta
        max, _ = scipy.signal.find_peaks(self._congwin)
        congwin_peak_avg = 1
        if len(self._congwin[max]) != 0:
            congwin_peak_avg = np.max(self._congwin[max])

        max, _ = scipy.signal.find_peaks(self._acks_in_process)
        response_peak_avg = 0
        if len(self._acks_in_process[max]) != 0:
            response_peak_avg = np.max(
                self._acks_in_process[max]
            )  # - self._calculate_shift_bytes()
        print("BASE len", len(self._base_cwnd))
        print("peak", response_peak_avg)

        self._congwin_to_response_ratio.append(
            (
                response_peak_avg
                - self._base_cwnd[-1] * (1 - self.base_to_amplitude_ratio)
            )
            / (
                congwin_peak_avg
                - self._base_cwnd[-1] * (1 - self.base_to_amplitude_ratio)
            )
        )"""

    def generate_congwin_to_response_ratio(self):
        # empty queues
        if (
            self._congwin is None
            or len(self._congwin) == 0
            or self._acks_in_process is None
            or len(self._acks_in_process) == 0
        ):
            self._congwin_to_response_ratio.append(0.5)
            return

        # get max delta values of cwnd and response
        cwnd_max_diff = max(self._congwin) - self._base_cwnd[-1] * (
            1 - self.base_to_amplitude_ratio
        )
        response_max_diff = max(self._acks_in_process) - self._base_cwnd[-1] * (
            1 - self.base_to_amplitude_ratio
        )

        # overlap %
        self._congwin_to_response_ratio.append(response_max_diff / cwnd_max_diff)

    def get_congwin_response_delta(self):
        if self._congwin is None:
            self._congwin_to_response_ratio.append(0)
            return
        if len(self._congwin) == 0 or len(self._acks_in_process) == 0:
            print("RE")
            return

        # get congin peak and valley delta
        max, _ = scipy.signal.find_peaks(self._congwin)
        congwin_peak_avg = 1
        if len(self._congwin[max]) != 0:
            congwin_peak_avg = np.max(self._congwin[max])

        max, _ = scipy.signal.find_peaks(self._acks_in_process)
        response_peak_avg = 0
        if len(self._acks_in_process[max]) != 0:
            response_peak_avg = np.max(self._acks_in_process[max])

        return (congwin_peak_avg) - (response_peak_avg)

    def get_bdp_estimate(self):
        if len(self._acks_in_process) == 0:
            return
        peaks, _ = scipy.signal.find_peaks(self._acks_in_process)
        if len(peaks) != 0:
            return np.mean(self._acks_in_process[peaks])

    def update_processing(self):
        if len(self.input_queue) == 0:
            return
        (
            self._delta_t,
            congwin,
            self._raw_acks,
            latest_rtt,
            conwin_base,
            sent_bytes,
        ) = zip(*self.input_queue)
        self._congwin = np.array(congwin)
        self._sent_bytes = np.array(sent_bytes)
        self._acks_in_process = np.array(self._raw_acks)
        self.update_rtt(latest_rtt)
        self._rtts = latest_rtt
        self._base_cwnd = conwin_base
        # self._acks_in_process = self._congwin

        self.gen_uniform_delta_t(midpoint_aligned=False)
        # self.gen_uniform_delta_t(midpoint_aligned=True)

        self._acks_in_process = self.apply_filter(window=4)
        self._acks_in_process = self.apply_interpolation()
        self.generate_congwin_to_response_ratio()
        # self.apply_differential()
        # self._acks_in_process = self.apply_detrending()
        # self._acks_in_process = self.apply_windowing()
        # self._acks_in_process = self.apply_zero_padding(factor=4)

        # self.generate_fft()
        # self.generate_base_to_second_harmonic_ratio()

    # TODO average this in a probing manner for later
    def update_rtt(self, latest_rtt):
        self._rtt_estimate = latest_rtt[-1]
