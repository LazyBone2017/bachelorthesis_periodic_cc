import asyncio
import csv
import os
import time

import zmq

RAW_LOG = []
SCALED_LOG = []


class TimestampLogger:
    def __init__(self, ui_out, external_config, algo_instance):
        self.ui_out = ui_out
        if ui_out:
            self.socket = zmq.Context().socket(zmq.PUSH)
            self.socket.connect("tcp://127.0.0.1:5555")
        self.sampling_rate = external_config["cca"]["sampling_rate"]
        self.registry = {}
        self._start_time = time.monotonic()
        self.direct_out = None
        self.saved = False
        self.csv_length = external_config["out"]["out_after"]
        self.csv_name = external_config["out"]["filename"]
        self.external_config = external_config
        self.threshold = 0
        self.algo_instance = algo_instance

    def register_metric(self, name: str, func, cleanup_function=None):
        if name in self.registry:
            raise KeyError(f"metric {name} is already registerered")
        self.registry[name] = (func, cleanup_function)
        print("Metric Registered: ", name)

    def get_metric(self, name):
        if name not in self.registry:
            raise KeyError(f"metric {name} was not registered.")
        callback, _ = self.registry[name]
        return callback()

    def run_metric_cleanup(self, name):
        if name not in self.registry:
            raise KeyError(f"metric {name} was not registered.")
        _, cleanup = self.registry[name]
        if cleanup is None:
            return
        cleanup()

    def set_direct_out(self, direct_out):
        self.direct_out = direct_out

    def save_to_csv(self, filename, data, header=None):
        print("CWD:", os.getcwd())
        with open(filename + ".csv", mode="w", newline="") as f:
            writer = csv.writer(f)
            if header:
                writer.writerow(header)
            writer.writerows(data)
        print("WRITTEN to file")

    async def pass_timestamps(self):
        while True:
            delta_t = time.monotonic() - self._start_time
            if delta_t > self.threshold:
                print("----Running for", self.threshold, "s----", flush=True)
                self.threshold += 10

            timestamp = [delta_t]
            for name in self.external_config["cca"]["transferred_metrics"]:
                timestamp.append(self.get_metric(name))

            if self.ui_out:
                self.socket.send_json(timestamp)
            if self.direct_out is not None:
                self.direct_out(timestamp)

            SCALED_LOG.append(timestamp)

            # edit timestamp for raw data
            timestamp[1] = self.algo_instance.get_acked_byte_raw()
            timestamp[2] = self.algo_instance.get_sent_byte_raw()
            timestamp[4] = self.algo_instance.get_lost_byte_raw()
            RAW_LOG.append(timestamp)
            if (
                delta_t > self.csv_length
                or (delta_t > 2 and self.get_metric("acked_byte") == 0)
            ) and not self.saved:
                self.save_to_csv(
                    "../data_out/" + self.csv_name + "_raw",
                    RAW_LOG,
                    ["delta_t"] + self.external_config["cca"]["transferred_metrics"],
                )
                self.save_to_csv(
                    "../data_out/" + self.csv_name + "_scaled",
                    SCALED_LOG,
                    ["delta_t"] + self.external_config["cca"]["transferred_metrics"],
                )
                self.saved = True
            for name in self.external_config["cca"]["transferred_metrics"]:
                self.run_metric_cleanup(name)

            await asyncio.sleep(1 / self.sampling_rate)
