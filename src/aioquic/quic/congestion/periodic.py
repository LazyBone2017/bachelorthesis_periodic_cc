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
    K_MINIMUM_WINDOW,
    QuicCongestionControl,
    QuicRttMonitor,
    register_congestion_control,
)


K_LOSS_REDUCTION_FACTOR = 0.5

LOG = []
ACK_BYTES_SUM = 0
PACKET_LOG = []
SAVED = False


class OperationState(Enum):
    INCREASE = auto()
    STEP_UP = auto()
    STEP_DOWN = auto()
    STATIC = auto()
    SENSE = auto()


class PeriodicCongestionControl(QuicCongestionControl):
    """
    New Periodic congestion control.
    """

    def __init__(self, *, max_datagram_size: int, is_client=False) -> None:
        super().__init__(max_datagram_size=max_datagram_size)
        self._max_datagram_size = max_datagram_size
        self._congestion_recovery_start_time = 0.0
        self._congestion_stash = 0
        self._rtt_monitor = QuicRttMonitor()
        self._start_time = time.monotonic()
        self._base_cwnd = 1200  # baseline in bytes
        # self.congestion_window = 120000
        # self._amplitude = self._base_cwnd * 0.35  # 0.25
        self._base_to_amplitude_ratio = 0.15
        self._frequency = 1  # how fast it oscillates (in Hz)
        self.rtt_estimate = 0.1
        self.latest_rtt = 0.1
        self.sampling_interval = 0.2
        self.acked_bytes_in_interval = 0
        self.sent_bytes_in_interval = 0
        self.lost_byte_in_interval = 0
        self._operation_state = OperationState.INCREASE
        self.state_start_t = time.monotonic()
        self.saved = False
        self.threshold = 0
        self.is_client = is_client
        self.logger = TimestampLogger.TimestampLogger(
            1 / self.sampling_interval, self.is_client, self.is_client, self.is_client
        )

        self._analyzer_unit = AnalyzerUnit(
            modulation_frequency=self._frequency,
            sampling_rate=1 / self.sampling_interval,
            base_to_amplitude_ratio=self._base_to_amplitude_ratio,
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

    # RTT shold be determine sampling interval
    # Mod Freq determines modulation interval

    def reset_acked_byte(self):
        self.acked_bytes_in_interval = 0

    def reset_sent_byte(self):
        self.sent_bytes_in_interval = 0

    def reset_lost_byte(self):
        self.lost_byte_in_interval = 0

    def get_cwnd_base_next_step(self):
        next = self._base_cwnd * (
            1 + 2 * math.pi * self._base_to_amplitude_ratio * self._frequency * 0.05
        )

        return next

    def change_operation_state(self, state: OperationState):
        self.state_start_t = time.monotonic()
        self._operation_state = state
        print("Switching to: ", state)

    async def control(self):
        while True:
            self._analyzer_unit.update_processing()
            match (self._operation_state):
                case OperationState.INCREASE:
                    self._base_cwnd = self.get_cwnd_base_next_step()
                    if np.mean(self._analyzer_unit._congwin_to_response_ratio) < 0.3:
                        self.change_operation_state(OperationState.STEP_DOWN)
                case OperationState.STATIC:
                    if np.mean(self._analyzer_unit._congwin_to_response_ratio) > 0.6:
                        self.change_operation_state(OperationState.STEP_UP)
                    if np.mean(self._analyzer_unit._congwin_to_response_ratio) < 0.5:
                        self.change_operation_state(OperationState.STEP_DOWN)
                case OperationState.STEP_UP:
                    self._base_cwnd *= (
                        1
                        + self._base_to_amplitude_ratio
                        * self._analyzer_unit._congwin_to_response_ratio[-1]
                    )
                    self.change_operation_state(OperationState.SENSE)
                case OperationState.STEP_DOWN:
                    self._base_cwnd = self._analyzer_unit.get_bdp_estimate()
                    print("BASE SET TO:", self._base_cwnd)
                    self.change_operation_state(OperationState.SENSE)
                case OperationState.SENSE:
                    self.rtt_estimate = self._analyzer_unit.get_rtt_estimate()
                    self._base_to_amplitude_ratio = (
                        self._analyzer_unit.get_base_to_amplitude_ratio("SENSE")
                    )

                    if (
                        time.monotonic() - self.state_start_t
                        > self._analyzer_unit.input_queue.maxlen
                        * self.sampling_interval
                    ):
                        self.change_operation_state(OperationState.STATIC)

            await asyncio.sleep(self.sampling_interval)

    def rect_mod(self, sine):
        return 1 if sine >= 0 else -1

    def calculate_cwnd_base_from_bdp(self, bdp_estimate, cutoff_fraction):
        base = bdp_estimate / (
            1 + self._base_to_amplitude_ratio * (1 - cutoff_fraction)
        )
        print("BDP ESTIMATE:", bdp_estimate)
        print("SETTING BASE: ", self._base_cwnd, flush=True)
        return base

    async def modulate_congestion_window(self):
        while True:
            delta_t = time.monotonic() - self._start_time
            sine_component = math.sin(2 * math.pi * self._frequency * delta_t)

            # sine_component = self.rect_mod(sine_component)
            amplitude = self._base_cwnd * self._base_to_amplitude_ratio

            self.congestion_window = int(self._base_cwnd + amplitude * sine_component)

            # set update interval proportional to modulation frequency
            await asyncio.sleep(1 / (10 * self._frequency))

    def on_packet_acked(self, *, now: float, packet: QuicSentPacket) -> None:
        self.bytes_in_flight -= packet.sent_bytes
        self.acked_bytes_in_interval += packet.sent_bytes * (
            self.rtt_estimate / self.sampling_interval
        )

    def on_packet_sent(self, *, packet: QuicSentPacket) -> None:
        self.bytes_in_flight += packet.sent_bytes
        self.sent_bytes_in_interval += packet.sent_bytes * (
            self.rtt_estimate / self.sampling_interval
        )

    def on_packets_expired(self, *, packets: Iterable[QuicSentPacket]) -> None:
        print("Expired")
        for packet in packets:
            self.bytes_in_flight -= packet.sent_bytes

    def on_packets_lost(self, *, now: float, packets: Iterable[QuicSentPacket]) -> None:
        print("LOSS")
        lost_largest_time = 0.0
        for packet in packets:
            self.bytes_in_flight -= packet.sent_bytes
            lost_largest_time = packet.sent_time
            self.lost_byte_in_interval += packet.sent_bytes * (
                self.rtt_estimate / self.sampling_interval
            )

    def on_rtt_measurement(self, *, now: float, rtt: float) -> None:
        # check whether we should exit slow start
        self.latest_rtt = rtt


register_congestion_control("periodic", PeriodicCongestionControl)
