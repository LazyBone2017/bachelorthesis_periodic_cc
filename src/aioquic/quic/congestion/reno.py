import asyncio
from typing import Iterable

import TimestampLogger

from ..packet_builder import QuicSentPacket
from .base import (
    K_MINIMUM_WINDOW,
    QuicCongestionControl,
    QuicRttMonitor,
    register_congestion_control,
)

K_LOSS_REDUCTION_FACTOR = 0.5


class RenoCongestionControl(QuicCongestionControl):
    """
    New Reno congestion control.
    """

    def __init__(self, *, max_datagram_size: int, external_config) -> None:
        super().__init__(max_datagram_size=max_datagram_size)
        self._max_datagram_size = max_datagram_size
        self._congestion_recovery_start_time = 0.0
        self._congestion_stash = 0
        self._rtt_monitor = QuicRttMonitor()

        # addded for monitoring

        self.acked_bytes_in_interval = 0
        self.sent_bytes_in_interval = 0
        self.lost_byte_in_interval = 0

        self.rtt_estimate = 1
        self.sampling_interval = 1 / float(external_config["cca"]["sampling_rate"])
        self.logger = TimestampLogger.TimestampLogger(
            ui_out=True,
            external_config=external_config,
        )

        self.logger.register_metric("cwnd", lambda: self.congestion_window)
        self.logger.register_metric(
            "acked_byte",
            lambda: self.acked_bytes_in_interval,
            self.reset_acked_byte,
        )
        self.logger.register_metric("rtt", lambda: self.rtt_estimate)
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

        t = asyncio.create_task(self.logger.pass_timestamps())
        t.add_done_callback(
            lambda t: print("TASK FINISHED:", t, "EXCEPTION:", t.exception())
        )

    def reset_acked_byte(self):
        self.acked_bytes_in_interval = 0

    def reset_sent_byte(self):
        self.sent_bytes_in_interval = 0

    def reset_lost_byte(self):
        self.lost_byte_in_interval = 0

    def on_packet_acked(self, *, now: float, packet: QuicSentPacket) -> None:
        self.bytes_in_flight -= packet.sent_bytes

        # added for monitoring
        self.acked_bytes_in_interval += packet.sent_bytes * (
            self.rtt_estimate / self.sampling_interval
        )

        # don't increase window in congestion recovery
        if packet.sent_time <= self._congestion_recovery_start_time:
            return

        if self.ssthresh is None or self.congestion_window < self.ssthresh:
            # slow start
            self.congestion_window += packet.sent_bytes
        else:
            # congestion avoidance
            self._congestion_stash += packet.sent_bytes
            count = self._congestion_stash // self.congestion_window
            if count:
                self._congestion_stash -= count * self.congestion_window
                self.congestion_window += count * self._max_datagram_size

    def on_packet_sent(self, *, packet: QuicSentPacket) -> None:
        self.bytes_in_flight += packet.sent_bytes

        # monitoring
        self.sent_bytes_in_interval += packet.sent_bytes * (
            self.rtt_estimate / self.sampling_interval
        )

    def on_packets_expired(self, *, packets: Iterable[QuicSentPacket]) -> None:
        for packet in packets:
            self.bytes_in_flight -= packet.sent_bytes

    def on_packets_lost(self, *, now: float, packets: Iterable[QuicSentPacket]) -> None:
        print("LOSS", flush=True)
        lost_largest_time = 0.0
        for packet in packets:
            self.bytes_in_flight -= packet.sent_bytes
            lost_largest_time = packet.sent_time
            # monitoring
            self.lost_byte_in_interval += packet.sent_bytes * (
                self.rtt_estimate / self.sampling_interval
            )

        # start a new congestion event if packet was sent after the
        # start of the previous congestion recovery period.
        if lost_largest_time > self._congestion_recovery_start_time:
            self._congestion_recovery_start_time = now
            self.congestion_window = max(
                int(self.congestion_window * K_LOSS_REDUCTION_FACTOR),
                K_MINIMUM_WINDOW * self._max_datagram_size,
            )
            self.ssthresh = self.congestion_window

        # TODO : collapse congestion window if persistent congestion

    def on_rtt_measurement(self, *, now: float, rtt: float) -> None:
        # check whether we should exit slow start
        if self.ssthresh is None and self._rtt_monitor.is_rtt_increasing(
            now=now, rtt=rtt
        ):
            self.ssthresh = self.congestion_window

        # monitoring
        self.rtt_estimate = rtt


register_congestion_control("reno", RenoCongestionControl)
