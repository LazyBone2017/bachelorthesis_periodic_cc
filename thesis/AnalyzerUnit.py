from collections import deque

import numpy as np


class AnalyzerUnit:

    def __init__(
        self,
        config,
    ):
        self.metrics = {
            name: np.array([], dtype=float)
            for name in config["cca"]["transferred_metrics"]
        }
        self.metrics["delta_t"] = np.array([], dtype=float)
        self._config = config

        self._base_to_amplitude_ratio = float(
            config["cca"].get("base_to_amplitude_ratio", 1)
        )
        self._sampling_rate = float(config["cca"]["sampling_rate"])
        self._modulation_frequency = float(config["cca"].get("mod_rate", 1))
        self.input_queue = deque(
            maxlen=int(self._sampling_rate / self._modulation_frequency * 2)
        )

        self._rtt_estimate = 0.1

        self.congwin_to_response_ratio = deque(
            [0] * self.input_queue.maxlen, maxlen=self.input_queue.maxlen
        )
        self.loss_rate = deque(
            [0] * self.input_queue.maxlen, maxlen=self.input_queue.maxlen
        )

    def update_processing(self):
        if len(self.input_queue) == 0:
            return
        arr = np.array(self.input_queue)
        self.metrics = {
            name: arr[:, i]
            for i, name in enumerate(
                ["delta_t"] + self._config["cca"]["transferred_metrics"]
            )
        }

        self._update_rtt(self.metrics["rtt"])
        self._generate_congwin_to_response_ratio()
        self._generate_loss_rate()

    def add_to_queue(self, entry):
        self.input_queue.append(entry)

    def get_rtt_estimate(self):
        if len(self.metrics["rtt"]) != 0:
            return np.min(self.metrics["rtt"])
        else:
            return 0.5  # fallback, should be more robust

    def get_bdp_estimate(self):
        if len(self.metrics["acked_byte"]) == 0:
            return
        return np.max(self.metrics["acked_byte"])

    def _generate_congwin_to_response_ratio(self):
        if (
            self.metrics["cwnd"] is None
            or len(self.metrics["cwnd"]) == 0
            or self.metrics["acked_byte"] is None
            or len(self.metrics["acked_byte"]) == 0
            or self.metrics.get("cwnd_base", [1])[-1] is None
            or max(self.metrics["acked_byte"]) == 0
        ):
            self.congwin_to_response_ratio.append(0.5)
            return

        self.congwin_to_response_ratio.append(
            (max(self.metrics["cwnd"]) - max(self.metrics["acked_byte"]))
            / (
                2
                * self.metrics.get("cwnd_base", [1])[-1]
                * self._base_to_amplitude_ratio
            )
        )

    def _generate_loss_rate(self):
        rate = sum(self.metrics["lost_byte"], 0) / sum(self.metrics["sent_byte"], 1)
        self.loss_rate.append(rate)

    def _update_rtt(self, latest_rtt):
        self._rtt_estimate = np.min(latest_rtt)
