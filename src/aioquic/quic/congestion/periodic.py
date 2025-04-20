import csv
import math
import os
import time
from typing import Any, Dict, Iterable

from ..packet_builder import QuicSentPacket
from .base import (
    K_MINIMUM_WINDOW,
    QuicCongestionControl,
    QuicRttMonitor,
    register_congestion_control,
)

K_LOSS_REDUCTION_FACTOR = 0.5
PKT_TRANSPORT_LOG = []



class PeriodicCongestionControl(QuicCongestionControl):
    """
    New Periodic congestion control.
    """

    def __init__(self, *, max_datagram_size: int) -> None:
        super().__init__(max_datagram_size=max_datagram_size)
        self._max_datagram_size = max_datagram_size
        self._congestion_recovery_start_time = 0.0
        self._congestion_stash = 0
        self._rtt_monitor = QuicRttMonitor()
        self._start_time = time.time()
        self._base_cwnd = 10000  # baseline in bytes
        self._amplitude = 8000   # how much the window fluctuates
        self._frequency = 5    # how fast it oscillates (in Hz)   


    def _update_congestion_window(self) -> None:
        # Get elapsed time for sine wave modulation
        elapsed_time = time.time() - self._start_time
        # Apply sine wave to base congestion window
        sine_factor = math.sin(2 * math.pi * self._frequency * elapsed_time)
        self.congestion_window = max(int(self._base_cwnd + self._amplitude * sine_factor), K_MINIMUM_WINDOW * self._max_datagram_size)
        
        


    def on_packet_acked(self, *, now: float, packet: QuicSentPacket) -> None:
        #PKT_TRANSPORT_LOG.append(["ACK", packet.packet_number, time.time()])
        self._update_congestion_window()  # Update window size
        self.bytes_in_flight -= packet.sent_bytes

        if packet.sent_time <= self._congestion_recovery_start_time:
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
                 self.congestion_window += count * self._max_datagram_size


    def on_packet_sent(self, *, packet: QuicSentPacket) -> None:
        self.bytes_in_flight += packet.sent_bytes
        PKT_TRANSPORT_LOG.append(["SENT", time.time(), packet.packet_number])

    def on_packets_expired(self, *, packets: Iterable[QuicSentPacket]) -> None:
        for packet in packets:
            self.bytes_in_flight -= packet.sent_bytes

    def on_packets_lost(self, *, now: float, packets: Iterable[QuicSentPacket]) -> None:
        print("LOSS")
        lost_largest_time = 0.0
        for packet in packets:
            self.bytes_in_flight -= packet.sent_bytes
            lost_largest_time = packet.sent_time

        if lost_largest_time > self._congestion_recovery_start_time:
            self._congestion_recovery_start_time = now
            self.congestion_window = max(
               int(self.congestion_window * K_LOSS_REDUCTION_FACTOR),
               K_MINIMUM_WINDOW * self._max_datagram_size,
           )
            self.ssthresh = self.congestion_window

        self._update_congestion_window()  # Modulate window after loss event


    def on_rtt_measurement(self, *, now: float, rtt: float) -> None:
        # check whether we should exit slow start
        if self.ssthresh is None and self._rtt_monitor.is_rtt_increasing(
            now=now, rtt=rtt
        ):
            self.ssthresh = self.congestion_window



register_congestion_control("periodic", PeriodicCongestionControl)
