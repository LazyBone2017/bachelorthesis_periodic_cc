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
        self._base_cwnd = 100000  # baseline in bytes
        self._amplitude = 10000  # how much the window fluctuates
        self._frequency = 1  # how fast it oscillates (in Hz)
        self.latest_rtt = 0
        self.is_client = is_client
        asyncio.create_task(self.modulate_congestion_window())

        if is_client:
            plt.ion()
            fig, (self.ax_time, self.ax_freq) = plt.subplots(
                1, 2, figsize=(10, 4)
            )  # 1 row, 2 columns
            axbox = fig.add_axes(
                [0.1, 0.01, 0.8, 0.05]
            )  # [left, bottom, width, height]
            text_box = TextBox(axbox, "Enter value:", initial="1")
            text_box.on_submit(lambda: print("TEST"))
            self.vals = deque(maxlen=100)
            self.vals.append((time.monotonic(), self.congestion_window))
            timestamps, congwin = zip(*self.vals)

            (self.line_time,) = self.ax_time.plot(
                timestamps, congwin, "b-"
            )  # Blue line for the graph

            (self.line_freq,) = self.ax_freq.plot(
                timestamps, 0, "b-"
            )  # Blue line for the graph

    def update_graph(self):
        return

    async def modulate_congestion_window(self):
        while True:
            delta_t = time.monotonic() - self._start_time
            new_conw = int(
                self._base_cwnd
                + self._amplitude * math.sin(2 * math.pi * self._frequency * delta_t)
            )

            # increase base rate on every upturn for testing
            """if self.congestion_window < self._base_cwnd and new_conw > self._base_cwnd:
                self._base_cwnd += 300"""

            # self._base_cwnd += 20

            self.congestion_window = new_conw
            global ACK_BYTES_SUM
            LOG.append(
                [
                    delta_t,
                    self.congestion_window,
                    self.bytes_in_flight,
                    self.latest_rtt
                    * 10000,  # scale so it can be displayed in the same graph
                ]
            )
            ACK_BYTES_SUM = 0

            if self.is_client:
                self.vals.append((time.monotonic(), self.bytes_in_flight))
                timestamps, congwin = zip(*self.vals)

                self.line_time.set_xdata(timestamps)
                self.line_time.set_ydata(congwin)
                self.ax_time.relim()
                self.ax_time.autoscale_view()

                fft = np.fft.fft(congwin - np.mean(congwin))
                freqs = np.fft.fftfreq(
                    len(congwin - np.mean(congwin)), d=(timestamps[1] - timestamps[0])
                )
                self.line_freq.set_xdata(freqs)
                self.line_freq.set_ydata(np.abs(fft))
                self.ax_freq.relim()
                self.ax_freq.autoscale_view()

                plt.draw()
                plt.pause(0.05)
            # set update frequency, inv. proportional to modulation frequency
            # await asyncio.sleep(0.001 / self._frequency)  # good constant is 0.001

    def on_packet_acked(self, *, now: float, packet: QuicSentPacket) -> None:
        self.bytes_in_flight -= packet.sent_bytes
        global ACK_BYTES_SUM
        ACK_BYTES_SUM += packet.sent_bytes
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
