import asyncio
import csv
import os
import time

import zmq

LOG = []


class TimestampLogger:
    def __init__(self, sampling_rate, ui_out=False, file_out=False):
        self.ui_out = ui_out
        if ui_out:
            self.socket = zmq.Context().socket(zmq.PUSH)
            self.socket.connect("tcp://127.0.0.1:5555")
        self.sampling_rate = sampling_rate
        self.metrics = []
        self._start_time = time.monotonic()
        self.direct_out = None
        self.saved = False
        self.csv_length = 300

        self.threshold = 0

    def register_metric(self, name: str, func, cleanup_function=None):
        self.metrics.append((name, func, cleanup_function))

    def set_direct_out(self, direct_out):
        self.direct_out = direct_out

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
                print("----Running for", self.threshold, "s----", flush=True)
                self.threshold += 10
            timestamp = tuple(func() for (name, func, cleanup) in self.metrics)
            timestamp = (delta_t,) + timestamp
            if self.ui_out:
                self.socket.send_json(timestamp)
            if self.direct_out is not None:
                self.direct_out(timestamp)
            LOG.append(timestamp)
            if delta_t > self.csv_length and not self.saved:
                self.save_to_csv("../data_out/data", LOG)
                self.saved = True
            for name, func, cleanup in self.metrics:
                if cleanup is not None:
                    cleanup()

            await asyncio.sleep(1 / self.sampling_rate)
