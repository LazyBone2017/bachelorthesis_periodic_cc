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
    STARTUP = auto()
    INCREASE = auto()
    MITIGATION = auto()
    STABLE = auto()


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
        self._base_cwnd = 30000  # baseline in bytes
        # self.congestion_window = 30000
        # self._amplitude = self._base_cwnd * 0.35  # 0.25
        self._base_to_amplitude_ratio = 0.25
        self._frequency = 1  # how fast it oscillates (in Hz)
        self.latest_rtt = 0.1
        self.rtt_estimate = 0.1
        self.sampling_interval = 0.2
        self.acked_bytes_in_interval = 0
        self.sent_bytes_in_interval = 0
        self._operation_state = OperationState.STARTUP
        self.saved = False
        self.threshold = 0

        self.is_client = is_client
        if is_client:
            self.socket = zmq.Context().socket(zmq.PUSH)
            self.socket.connect("tcp://127.0.0.1:5555")

        self._analyzer_unit = AnalyzerUnit(
            modulation_frequency=self._frequency,
            sampling_rate=1 / self.sampling_interval,
        )

        mod = asyncio.create_task(self.modulate_congestion_window())
        mod.add_done_callback(
            lambda t: print("TASK FINISHED:", t, "EXCEPTION:", t.exception())
        )
        t = asyncio.create_task(self.pass_timestamps())
        t.add_done_callback(
            lambda t: print("TASK FINISHED:", t, "EXCEPTION:", t.exception())
        )
        c = asyncio.create_task(self.control())
        c.add_done_callback(
            lambda t: print("TASK FINISHED:", t, "EXCEPTION:", t.exception())
        )

    # RTT shold be determine sampling interval
    # Mod Freq determines modulation interval

    async def control(self):
        while True:
            self._analyzer_unit.update_processing()
            self.rtt_estimate = self._analyzer_unit.get_rtt_estimate()
            match self._operation_state:
                case OperationState.STARTUP:
                    # end of startup
                    if np.mean(self._analyzer_unit._congwin_to_response_ratio) > 0.9:
                        print("SWITCH TO INCREASE")
                        self._operation_state = OperationState.INCREASE
                case OperationState.INCREASE:
                    if np.mean(self._analyzer_unit._congwin_to_response_ratio) < 0.8525:
                        print("SWITCH TO MITIGATE")
                        self._operation_state = OperationState.MITIGATION
                case OperationState.MITIGATION:
                    if np.mean(self._analyzer_unit._congwin_to_response_ratio) >= 0.825:
                        print("SWITCH TO STABLE")
                        self._operation_state = OperationState.STABLE
                case OperationState.STABLE:
                    # BDP has decreased
                    if np.mean(self._analyzer_unit._congwin_to_response_ratio) < 0.825:
                        print("SWITCH TO MITIGATION")
                        self._operation_state = OperationState.MITIGATION
                        # BDP has increased
                    if np.mean(self._analyzer_unit._congwin_to_response_ratio) > 0.9:
                        print("SWITCH TO INCREASE")
                        self._operation_state = OperationState.INCREASE
                case _:
                    print("INVALID OperationState")
            await asyncio.sleep(self.sampling_interval)

    def rect_mod(self, sine):
        return 1 if sine >= 0 else -1

    async def modulate_congestion_window(self):
        while True:
            delta_t = time.monotonic() - self._start_time
            increase_per_second = 5000
            sine_component = math.sin(2 * math.pi * self._frequency * delta_t)
            sine_component = self.rect_mod(sine_component)
            # sine_component = 0
            amplitude = self._base_cwnd * self._base_to_amplitude_ratio  # no effect
            if self._operation_state == OperationState.INCREASE:
                self._base_cwnd += increase_per_second / 10
            if self._operation_state == OperationState.MITIGATION:
                self._base_cwnd = self._analyzer_unit.get_bdp_estimate() * 0.95
                print("SETTING BASE: ", self._base_cwnd)
            if self._operation_state == OperationState.STABLE:
                x = 1  # only to have a visible case, cwnd_base doesnt chan

            new_conw = int(self._base_cwnd + amplitude * sine_component)
            increase_per_second = 5000
            self.congestion_window = new_conw

            # set update interval proportional to modulation frequency
            await asyncio.sleep(1 / (10 * self._frequency))

    def save_to_csv(self, filename, data):
        print("CWD:", os.getcwd())
        with open(filename + ".csv", mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print("WRITTEN to file")

    async def pass_timestamps(self):
        while True:
            delta_t = time.monotonic() - self._start_time
            if delta_t > self.threshold:
                print("----Running for", self.threshold, "s----")
                self.threshold += 30
            timestamp = (
                delta_t,
                self.congestion_window,
                self.acked_bytes_in_interval,
                self.latest_rtt,
                self._base_cwnd,
                self.sent_bytes_in_interval,
            )
            self.socket.send_json(timestamp)
            self._analyzer_unit.input_queue.append(timestamp)
            LOG.append(timestamp)
            if delta_t > 600 and not self.saved:
                self.save_to_csv("../data_out/data", LOG)
                self.saved = True
                print("SAVE")
            self.acked_bytes_in_interval = 0
            self.sent_bytes_in_interval = 0

            await asyncio.sleep(self.sampling_interval)

    def on_packet_acked(self, *, now: float, packet: QuicSentPacket) -> None:
        self.bytes_in_flight -= packet.sent_bytes
        self.acked_bytes_in_interval += packet.sent_bytes * (
            self.rtt_estimate / self.sampling_interval
        )
        """if packet.sent_time <= self._congestion_recovery_start_time:
            return

        if self.ssthresh is None or self.congestion_window < self.ssthresh:
            # Slow start
            self.congestion_window += packet.sent_bytes
        else:
            # Congestion avoidance
            self._congestion_stash += packet.sent_bytes
            count = self._congestion_stash // self.congestion_window
            if count:
                 self._congestion_stash -= count * self.congestion_window
                 self.congestion_window += count * self._max_datagram_size"""

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

        # start congestion recovery
        """if lost_largest_time > self._congestion_recovery_start_time:
            self._congestion_recovery_start_time = now
            self.congestion_window = max(
               int(self.congestion_window * K_LOSS_REDUCTION_FACTOR),
               K_MINIMUM_WINDOW * self._max_datagram_size,
           )
            self.ssthresh = self.congestion_window"""

    def on_rtt_measurement(self, *, now: float, rtt: float) -> None:
        # check whether we should exit slow start
        self.latest_rtt = rtt
        return
        if self.ssthresh is None and self._rtt_monitor.is_rtt_increasing(
            now=now, rtt=rtt
        ):
            self.ssthresh = self.congestion_window


register_congestion_control("periodic", PeriodicCongestionControl)
