from collections import deque
import math

from matplotlib.mlab import detrend
import numpy as np
import scipy
import scipy.signal


# unit holds a single version of all processing applied _acks_in_process, saving intermediary states in dedicated fields


class AnalyzerUnit:
    def __init__(
        self,
        sampling_rate,
        modulation_frequency,
        base_to_amplitude_ratio,
        external_config,
    ):
        self.metrics = {
            name: np.array([], dtype=float)
            for name in external_config["cca"]["transferred_metrics"]
        }
        self.metrics["delta_t"] = np.array([], dtype=float)
        self.external_config = external_config
        self.base_to_amplitude_ratio = base_to_amplitude_ratio
        self._sampling_rate = sampling_rate
        self._modulation_frequency = modulation_frequency
        self.input_queue = deque(maxlen=int(sampling_rate / modulation_frequency * 2))

        self._acks_in_process = [0] * self.input_queue.maxlen

        self._delta_t_uniform = [0] * self.input_queue.maxlen
        self._filtered_acks = [0] * self.input_queue.maxlen
        self._interpolated_acks = [0] * self.input_queue.maxlen

        self._rtt_estimate = 0.1

        self._base_to_second_harmonic_ratio = deque(
            [0] * self.input_queue.maxlen, maxlen=self.input_queue.maxlen
        )
        self._congwin_to_response_ratio = deque(
            [0] * self.input_queue.maxlen, maxlen=self.input_queue.maxlen
        )
        self._loss_rate = deque(
            [0] * self.input_queue.maxlen, maxlen=self.input_queue.maxlen
        )

    def add_to_queue(self, entry):
        self.input_queue.append(entry)

    def gen_uniform_delta_t(self):
        self._delta_t_uniform = np.arange(
            self.metrics["delta_t"][0],
            self.metrics["delta_t"][-1],
            1 / self._sampling_rate,
        )

    def get_rtt_estimate(self):
        if len(self.metrics["rtt"]) != 0:
            return np.min(self.metrics["rtt"])
        else:
            return 0.5  # fallback, is this good?

    def apply_interpolation(self):
        if len(self._acks_in_process) == 0:
            return
        self._interpolated_acks = np.interp(
            self._delta_t_uniform, self.metrics["delta_t"], self._acks_in_process
        )
        return self._interpolated_acks

    def generate_congwin_to_response_ratio(self):
        # empty queues
        if (
            self.metrics["cwnd"] is None
            or len(self.metrics["cwnd"]) == 0
            or self._acks_in_process is None
            or len(self._acks_in_process) == 0
            or self.metrics["cwnd_base"][-1] is None
        ):
            self._congwin_to_response_ratio.append(0.5)
            return

        # get max delta values of cwnd and response

        self._congwin_to_response_ratio.append(
            (max(self.metrics["cwnd"]) - max(self._acks_in_process))
            / (2 * self.metrics["cwnd_base"][-1] * self.base_to_amplitude_ratio)
        )

    def get_bdp_estimate(self):
        print("ACKS LEN", len(self._acks_in_process))
        if len(self._acks_in_process) == 0:
            return

        print("ESTIMATE", np.max(self._acks_in_process))
        return np.max(self._acks_in_process)

    def generate_loss_rate(self):
        rate = sum(self.metrics["lost_byte"], 0) / sum(self.metrics["sent_byte"], 1)
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
        arr = np.array(self.input_queue)
        self.metrics = {
            name: arr[:, i]
            for i, name in enumerate(
                ["delta_t"] + self.external_config["cca"]["transferred_metrics"]
            )
        }

        self.update_rtt(self.metrics["rtt"])
        self.gen_uniform_delta_t()
        self._acks_in_process = self.metrics["acked_byte"]
        self._acks_in_process = self.apply_interpolation()
        self.generate_congwin_to_response_ratio()
        self.generate_loss_rate()

    # TODO average this in a probing manner for later
    def update_rtt(self, latest_rtt):
        self._rtt_estimate = min(latest_rtt)
