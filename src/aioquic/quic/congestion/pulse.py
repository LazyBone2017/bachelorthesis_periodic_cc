import asyncio
from collections import deque
import csv
from enum import Enum, auto
import math
import os
import time
import threading
from typing import Any, Dict, Iterable

from matplotlib import pyplot as plt
from matplotlib.widgets import TextBox
import numpy as np
import zmq

from AnalyzerUnit import AnalyzerUnit
import TimestampLogger

from ..packet_builder import QuicSentPacket
from .base import (
    QuicCongestionControl,
    QuicRttMonitor,
    register_congestion_control,
)


class OperationState(Enum):
    STARTUP = auto()
    INCREASE = auto()
    CORRECT = auto()
    STATIC = auto()
    SENSE = auto()


class PulseCongestionControl(QuicCongestionControl):
    """
    New PULSE congestion control.
    """

    def __init__(self, *, max_datagram_size: int, external_config) -> None:
        super().__init__(max_datagram_size=max_datagram_size)
        self._max_datagram_size = max_datagram_size
        self._congestion_recovery_start_time = 0.0
        self._congestion_stash = 0
        self._rtt_monitor = QuicRttMonitor()
        self._start_time = time.monotonic()

        self._base_cwnd = float(external_config["cca"]["cwnd_base_0"])
        self._base_to_amplitude_ratio = float(
            external_config["cca"]["base_to_amplitude_ratio"]
        )
        self._frequency = float(external_config["cca"]["mod_rate"])
        self.sampling_interval = 1 / float(external_config["cca"]["sampling_rate"])

        self.rtt_estimate = external_config["cca"]["initial_rtt"]
        self.latest_rtt = external_config["cca"]["initial_rtt"]
        self.phi = external_config["cca"]["phi"]
        self.increase_percentile = external_config["cca"]["increase_percentile"]
        self.waveform = external_config["cca"]["waveform"]

        self.acked_bytes_in_interval = 0
        self.sent_bytes_in_interval = 0
        self.lost_byte_in_interval = 0

        self.acked_byte_raw = 0
        self.sent_byte_raw = 0
        self.lost_byte_raw = 0

        self._operation_state = OperationState.STARTUP
        self.state_start_t = time.monotonic()
        self.supressed_loss = 0
        self.saved = False
        self.threshold = 0
        self.logger = TimestampLogger.TimestampLogger(
            ui_out=True, external_config=external_config, algo_instance=self
        )

        self._analyzer_unit = AnalyzerUnit(
            config=external_config,
        )

        self.logger.set_direct_out(self._analyzer_unit.add_to_queue)

        self.logger.register_metric("cwnd", lambda: self.congestion_window)
        self.logger.register_metric(
            "acked_byte", lambda: self.acked_bytes_in_interval, self.reset_acked_byte
        )
        self.logger.register_metric("rtt", lambda: self.latest_rtt)
        self.logger.register_metric(
            "cwnd_base",
            lambda: self._base_cwnd,
        )
        self.logger.register_metric(
            "sent_byte",
            lambda: self.sent_bytes_in_interval,
            cleanup_function=self.reset_sent_byte,
        )
        self.logger.register_metric(
            "lost_byte",
            lambda: self.lost_byte_in_interval,
            cleanup_function=self.reset_lost_byte,
        )

        mod = asyncio.create_task(self.modulate_congestion_window())
        mod.add_done_callback(
            lambda t: print("TASK FINISHED:", t, "EXCEPTION:", t.exception())
        )
        t = asyncio.create_task(self.logger.pass_timestamps())
        t.add_done_callback(
            lambda t: print("TASK FINISHED:", t, "EXCEPTION:", t.exception())
        )
        c = asyncio.create_task(self.control())
        c.add_done_callback(
            lambda t: print("TASK FINISHED:", t, "EXCEPTION:", t.exception())
        )
        print("config read @PULSE")

    def get_acked_byte_raw(self):
        temp = self.acked_byte_raw
        self.acked_byte_raw = 0
        return temp

    def get_sent_byte_raw(self):
        temp = self.sent_byte_raw
        self.sent_byte_raw = 0
        return temp

    def get_lost_byte_raw(self):
        temp = self.lost_byte_raw
        self.lost_byte_raw = 0
        return temp

    def reset_acked_byte(self):
        self.acked_bytes_in_interval = 0

    def reset_sent_byte(self):
        self.sent_bytes_in_interval = 0

    def reset_lost_byte(self):
        self.lost_byte_in_interval = 0

    def get_cwnd_base_next_step(self):
        next = self._base_cwnd * (
            1 + 2 * math.pi * self._base_to_amplitude_ratio * self._frequency * self.phi
        )

        return next

    def change_operation_state(self, state: OperationState):
        if state == OperationState.SENSE:
            self.supressed_loss = 0
        self.state_start_t = time.monotonic()
        self._operation_state = state
        print("Switching to: ", state)

    def state_active_over(self, t):
        return time.monotonic() - self.state_start_t > t

    async def control(self):
        while True:
            self._analyzer_unit.update_processing()
            match (self._operation_state):
                case OperationState.STARTUP:
                    if (
                        self.state_active_over(
                            self._analyzer_unit.input_queue.maxlen
                            * self.sampling_interval
                        )
                        * 2
                    ):
                        self.rtt_estimate = self._analyzer_unit.get_rtt_estimate()

                        self.change_operation_state(OperationState.INCREASE)
                case OperationState.INCREASE:
                    self._base_cwnd = self.get_cwnd_base_next_step()
                    mean = np.percentile(
                        self._analyzer_unit.congwin_to_response_ratio,
                        self.increase_percentile,
                    )
                    if mean > 0.5:
                        print(self._base_cwnd)
                        self.change_operation_state(OperationState.CORRECT)
                case OperationState.STATIC:
                    mean = np.mean(self._analyzer_unit.congwin_to_response_ratio)
                    if mean < 0.4:
                        self.change_operation_state(OperationState.CORRECT)
                    elif mean > 0.5:
                        self.change_operation_state(OperationState.CORRECT)
                case OperationState.CORRECT:
                    base = self._analyzer_unit.get_bdp_estimate()
                    if base is not None:
                        print(
                            "STEP DOWN" if self._base_cwnd > base else "STEP UP",
                            "BASE SET TO:",
                            base,
                        )
                        self._base_cwnd = base
                    self.change_operation_state(OperationState.SENSE)
                case OperationState.SENSE:
                    self.rtt_estimate = self._analyzer_unit.get_rtt_estimate()

                    if self.state_active_over(
                        self._analyzer_unit.input_queue.maxlen * self.sampling_interval
                    ):
                        self.change_operation_state(OperationState.STATIC)

            await asyncio.sleep(self.sampling_interval)

    async def modulate_congestion_window(self):
        while True:
            delta_t = time.monotonic() - self._start_time
            periodic_component = None
            match (self.waveform):
                case "sine":
                    periodic_component = math.sin(2 * math.pi * self._frequency * delta_t)
                case "square":
                    periodic_component = 1 if ((self._frequency * delta_t) % 1) < 0.5 else -1
                case "triangle":
                    periodic_component = 4 * abs((self._frequency * delta_t) % 1 - 0.5) - 1
                case "saw":
                    periodic_component = 2 * ((self._frequency * delta_t) % 1) - 1

            amplitude = self._base_cwnd * self._base_to_amplitude_ratio
            self.congestion_window = int(self._base_cwnd + amplitude * periodic_component)

            await asyncio.sleep(self.sampling_interval)

    def on_packet_acked(self, *, now: float, packet: QuicSentPacket) -> None:
        self.bytes_in_flight -= packet.sent_bytes
        self.acked_bytes_in_interval += packet.sent_bytes * (
            self.rtt_estimate / self.sampling_interval
        )
        self.acked_byte_raw += packet.sent_bytes

    def on_packet_sent(self, *, packet: QuicSentPacket) -> None:
        self.bytes_in_flight += packet.sent_bytes
        self.sent_bytes_in_interval += packet.sent_bytes * (
            self.rtt_estimate / self.sampling_interval
        )

        self.sent_byte_raw += packet.sent_bytes

    def on_packets_expired(self, *, packets: Iterable[QuicSentPacket]) -> None:
        for packet in packets:
            self.bytes_in_flight -= packet.sent_bytes

    def on_packets_lost(self, *, now: float, packets: Iterable[QuicSentPacket]) -> None:
        for packet in packets:
            self.bytes_in_flight -= packet.sent_bytes
            self.lost_byte_in_interval += packet.sent_bytes * (
                self.rtt_estimate / self.sampling_interval
            )
            self.lost_byte_raw += packet.sent_bytes

    def on_rtt_measurement(self, *, now: float, rtt: float) -> None:
        self.latest_rtt = rtt


register_congestion_control("pulse", PulseCongestionControl)
