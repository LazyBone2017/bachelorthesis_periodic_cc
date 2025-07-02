import asyncio
from collections import deque
import csv
import math
import os
import time
import threading
from typing import Any, Dict, Iterable

from matplotlib import pyplot as plt
from matplotlib.widgets import TextBox
import numpy as np
import zmq

from ModulationAnalyzer import ModulationAnalyzer

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
        self._base_cwnd = 40000  # baseline in bytes
        # self.congestion_window = 100000
        self._amplitude = 20000  # how much the window fluctuates
        self._frequency = 0.5  # how fast it oscillates (in Hz)
        self.latest_rtt = 0
        self.sampling_interval = 0.2
        self.acked_bytes_in_interval = 0

        self.is_client = is_client
        if is_client:
            self.socket = zmq.Context().socket(zmq.PUSH)
            self.socket.connect("tcp://127.0.0.1:5555")

        asyncio.create_task(self.modulate_congestion_window())
        asyncio.create_task(self.pass_timestamps())

    # RTT shold be determine sampling interval
    # Mod Freq determines modulation interval

    async def modulate_congestion_window(self):
        while True:
            delta_t = time.monotonic() - self._start_time
            linear_slope = 1000

            sine_component = math.sin(2 * math.pi * self._frequency * delta_t)
            amplitude = self._amplitude * (1.2 if sine_component < 0 else 1)
            new_conw = int(
                self._base_cwnd + amplitude * sine_component + delta_t * linear_slope
            )

            self.congestion_window = new_conw

            if self.is_client:
                """self.modulation_analyzer.update_samples(
                    self.congestion_window,
                    self.acked_bytes_in_interval,
                    delta_t,
                    self.latest_rtt,
                )
                self.socket.send_json(
                    (
                        delta_t,
                        self.congestion_window,
                        self.acked_bytes_in_interval,
                        self.latest_rtt,
                    )
                )  # Non-blocking send"""
                # self._frequency = self.modulation_analyzer.modulation_frequency

            # set update frequency, inv. proportional to modulation frequency
            await asyncio.sleep(1 / (10 * self._frequency))

    async def pass_timestamps(self):
        while True:
            self.socket.send_json(
                (
                    time.monotonic() - self._start_time,
                    self.congestion_window,
                    self.acked_bytes_in_interval,
                    self.latest_rtt,
                )
            )
            self.acked_bytes_in_interval = 0

            await asyncio.sleep(self.sampling_interval)

    def on_packet_acked(self, *, now: float, packet: QuicSentPacket) -> None:
        self.bytes_in_flight -= packet.sent_bytes
        self.acked_bytes_in_interval += packet.sent_bytes * (
            0.1 / self.sampling_interval
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
