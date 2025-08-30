from collections import deque
import math

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
        self.lost_byte = [0] * self.input_queue.maxlen

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
            [0] * self.input_queue.maxlen, maxlen=self.input_queue.maxlen
        )
        self._base_cwnd = deque(
            [0] * self.input_queue.maxlen, maxlen=self.input_queue.maxlen
        )

        self._loss_rate = deque(
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

    def generate_congwin_to_response_ratio(self):
        # empty queues
        if (
            self._congwin is None
            or len(self._congwin) == 0
            or self._acks_in_process is None
            or len(self._acks_in_process) == 0
            or self._base_cwnd[-1] is None
        ):
            self._congwin_to_response_ratio.append(0.5)
            return

        # get max delta values of cwnd and response

        self._congwin_to_response_ratio.append(
            (max(self._congwin) - max(self._acks_in_process))
            / (2 * self._base_cwnd[-1] * self.base_to_amplitude_ratio)
        )

    def get_bdp_estimate(self):
        if len(self._acks_in_process) == 0:
            return
        peaks, _ = scipy.signal.find_peaks(self._acks_in_process)
        if len(peaks) != 0:
            return np.mean(self._acks_in_process[peaks])

    def generate_loss_rate(self):
        rate = sum(self.lost_byte, 0) / sum(self._sent_bytes, 1)
        self._loss_rate.append(rate)

    def get_base_to_amplitude_ratio(self, state):
        default_ratio = 0.25

        if (
            state == "SENSE"
        ):  # high loss here means shallow buffers -> decrease amplitude(but: remove baseline loss first)
            r = (
                default_ratio - np.average(self._loss_rate) * 2
            )  # const determines agressiveness
            return r

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
            lost_bytes,
        ) = zip(*self.input_queue)
        self._congwin = np.array(congwin)
        self._sent_bytes = np.array(sent_bytes)
        self._acks_in_process = np.array(self._raw_acks)
        self.lost_byte = np.array(lost_bytes)
        self.update_rtt(latest_rtt)
        self._rtts = latest_rtt
        self._base_cwnd = conwin_base
        # self._acks_in_process = self._congwin

        self.gen_uniform_delta_t(midpoint_aligned=False)
        # self.gen_uniform_delta_t(midpoint_aligned=True)

        self._acks_in_process = self.apply_filter(window=4)
        self._acks_in_process = self.apply_interpolation()
        self.generate_congwin_to_response_ratio()
        self.generate_loss_rate()

    # TODO average this in a probing manner for later
    def update_rtt(self, latest_rtt):
        self._rtt_estimate = min(latest_rtt)
