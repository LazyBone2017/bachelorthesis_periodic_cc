import asyncio
import csv
import os
import time

import zmq


class TimestampLogger:
    def __init__(self, ui_out, external_config, algo_instance):
        self.RAW_LOG = []
        self.SCALED_LOG = []
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
        self.single_file_mode = external_config["provider"]["single_file_mode"]
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
        directory = os.path.dirname(filename)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(filename + ".csv", mode="w", newline="") as f:
            writer = csv.writer(f)
            if header:
                writer.writerow(header)
            writer.writerows(data)
        print(f"Output written to: {filename}")

    async def pass_timestamps(self):
        while True:
            delta_t = time.monotonic() - self._start_time
            if delta_t > self.threshold:
                print("----Running for", self.threshold, "s----", flush=True)
                self.threshold += 10

            timestamp_scaled = [delta_t]
            timestamp_raw = [delta_t]
            for name in self.external_config["cca"]["transferred_metrics"]:
                timestamp_scaled.append(self.get_metric(name))
                timestamp_raw.append(self.get_metric(name))

            if self.ui_out:
                self.socket.send_json(timestamp_scaled)
            if self.direct_out is not None:
                self.direct_out(timestamp_scaled)

            self.SCALED_LOG.append(timestamp_scaled)

            # edit timestamp for raw data
            timestamp_raw[2] = self.algo_instance.get_acked_byte_raw()
            timestamp_raw[3] = self.algo_instance.get_sent_byte_raw()
            timestamp_raw[5] = self.algo_instance.get_lost_byte_raw()
            self.RAW_LOG.append(timestamp_raw)
            if (
                not self.single_file_mode
                and (delta_t > self.csv_length)
                or self.single_file_mode
                and (delta_t > 10 and self.get_metric("acked_byte") == 0)
            ) and not self.saved:
                filename_base = (
                    f"../data_out/{self.external_config['cca']['name']}/{self.csv_name}"
                )
                self.save_to_csv(
                    filename_base + "_raw",
                    self.RAW_LOG,
                    ["delta_t"] + self.external_config["cca"]["transferred_metrics"],
                )
                self.save_to_csv(
                    filename_base + "_scaled",
                    self.SCALED_LOG,
                    ["delta_t"] + self.external_config["cca"]["transferred_metrics"],
                )
                self.saved = True
            for name in self.external_config["cca"]["transferred_metrics"]:
                self.run_metric_cleanup(name)

            await asyncio.sleep(1 / self.sampling_rate)
