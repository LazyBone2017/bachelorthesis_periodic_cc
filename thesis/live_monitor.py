import argparse
from collections import deque
import os
import signal
import subprocess
import threading
import time

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from matplotlib import pyplot as plt
from matplotlib import animation
from matplotlib.widgets import Button
import numpy as np
import zmq

from AnalyzerUnit import AnalyzerUnit

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
args = parser.parse_args()

config = None
with open(args.config, "rb") as f:
    config = tomllib.load(f)
    print("config read @monitor")

_analyzer_unit = AnalyzerUnit(
    config=config,
)
save_log = deque()

fig = plt.figure(figsize=(19.2 * 0.8, 10.8 * 0.8), dpi=100)

axes = {}

axes["in"] = plt.subplot2grid((4, 2), (0, 0), colspan=2)

axes["out"] = plt.subplot2grid((4, 2), (1, 0), colspan=2)

axes["left"] = plt.subplot2grid((4, 2), (2, 0))

axes["right"] = plt.subplot2grid((4, 2), (2, 1))

axes["ratio"] = plt.subplot2grid((4, 2), (3, 0), colspan=2)

lines = {}


for ax in config["monitor"]["composition"]:
    for metric in config["monitor"]["composition"][ax]:
        (line,) = axes[ax].plot(
            [], [], label=f"{metric}({config['monitor']['units'][metric]})"
        )
        lines[(metric, ax)] = line

    axes[ax].legend(loc=2)

axes["left"].set_ylim(0, 0.5)

(lines[("crr", "ratio")],) = axes["ratio"].plot([], [], label="cwnd_resp_ratio")
(lines[("loss", "right")],) = axes["right"].plot([], [], label="Loss %")

axes["ratio"].set_ylim(0, 1)
axes["right"].set_ylim(0, 1.5)

axes["ratio"].legend(loc=2)
axes["right"].legend(loc=2)


process = [None]


def run_client():
    if process[0] is None or process[0].poll() is not None:
        process[0] = subprocess.Popen(
            ["bash", "./client_start.sh", args.config], preexec_fn=os.setsid
        )
        print("Shell script started as standalone process")
    else:
        print("Shell script already running")


def stop_client():
    if process[0] is not None and process[0].poll() is None:
        os.killpg(os.getpgid(process[0].pid), signal.SIGTERM)
        process[0].wait()
        process[0] = None
        print("Shell script stopped")
    else:
        print("No shell script running")


def handle_start_button(event):
    if process[0] is None:
        run_client()
        start_button.label.set_text("Running...\nPress to Stop")
    else:
        stop_client()
        _analyzer_unit.input_queue.clear()
        start_button.label.set_text("Run")


def on_close(event):
    print("Figure closed — cleaning up...")
    stop_client()


fig.canvas.mpl_connect("close_event", on_close)
start_button_ax = fig.add_axes([0.8, 0.01, 0.1, 0.075])
start_button = Button(start_button_ax, "Run")
start_button.on_clicked(handle_start_button)

manager = plt.get_current_fig_manager()
toolbar = getattr(manager, "toolbar", None)
if toolbar is not None and hasattr(toolbar, "pack_forget"):
    toolbar.pack_forget()


class DataReceiver:
    def __init__(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PULL)
        self.socket.bind("tcp://127.0.0.1:5555")

    def update_source(self):
        while True:
            try:
                data = self.socket.recv_json(flags=zmq.NOBLOCK)
                _analyzer_unit.input_queue.append(data)
                save_log.append(data)
                time.sleep(0.1)
            except zmq.Again:
                time.sleep(0.1)
                # no message ready
                pass


def update(i):
    _analyzer_unit.update_processing()

    for ax in config["monitor"]["composition"]:
        for metric in config["monitor"]["composition"][ax]:
            lines[(metric, ax)].set_data(
                _analyzer_unit.metrics["delta_t"], _analyzer_unit.metrics[metric]
            )

        axes[ax].autoscale_view()
        axes[ax].relim()

    crr = _analyzer_unit._congwin_to_response_ratio
    lines["crr", "ratio"].set_data(
        np.arange(len(crr)),
        crr,
    )
    lines["loss", "right"].set_data(
        np.arange(len(_analyzer_unit._loss_rate)),
        np.array(_analyzer_unit._loss_rate) * 100,
    )  # convert to percent

    axes["right"].autoscale_view()
    axes["ratio"].autoscale_view()

    axes["right"].relim()
    axes["ratio"].relim()


receiver = DataReceiver()
threading.Thread(target=receiver.update_source, daemon=True).start()
ani = animation.FuncAnimation(fig, update, interval=32)
plt.show()
