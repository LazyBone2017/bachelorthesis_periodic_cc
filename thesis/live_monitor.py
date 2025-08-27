from collections import deque
import os
import signal
import subprocess
import threading
import time
from matplotlib import pyplot as plt
from matplotlib import animation
from matplotlib.widgets import Button
import numpy as np
import zmq

from AnalyzerUnit import AnalyzerUnit


# data_queue = deque(maxlen=1000)
_analyzer_unit = AnalyzerUnit(
    sampling_rate=5, modulation_frequency=1, base_to_amplitude_ratio=0.15
)
save_log = deque()


fig, (ax1, ax2, ax3, ax4) = plt.subplots(
    4, 1, figsize=(19.2 * 0.8, 10.8 * 0.8), dpi=100
)
plt.subplots_adjust(bottom=0.2)
(line1,) = ax1.plot([], [])
(line1b,) = ax1.plot([], [])
(line1c,) = ax1.plot([], [], label="Sent_bytes", color="red")
(line2a,) = ax2.plot([], [], label="Acked Bytes")
(line2b,) = ax2.plot([], [], label="Acked Bytes Filtered", color="red")
(line2c,) = ax2.plot([], [], label="Acked Bytes Filtered Interpolated", color="orange")
"""(line2d,) = ax2.plot(
    [], [], label="Acked Bytes Filtered Interpolated Detrended", color="orange"
)
(line2e,) = ax2.plot(
    [], [], label="Acked Bytes Filtered Interpolated Detrended Windowed", color="pink"
)"""
(line3a,) = ax3.plot([], [], label="Ratio", color="red")
(line3b,) = ax3.plot([], [], label="Ratio Avg", color="blue")

(line4,) = ax4.plot([], [], label="Conwin/Response")
(line4b,) = ax4.plot([], [], label="Lost Byte % x10")
# (line4b,) = ax4.plot([], [], label="Savgol Hanning 0-Pad FFT", color="red")


ax1.set_ylabel("Congwin(Byte)")
ax2.set_ylabel("Acked(Byte)")
# ax3.set_ylabel("RTT(s)")
# ax3.set_xlabel("Time(s)")
ax3.set_xlabel("Time(s)")
ax3.set_ylabel("Base to 2nd Harmonic Ratio")
ax4.set_xlabel("Frequency(Hz)")
ax4.set_ylabel("Magnitude")

ax2.legend(loc=1)
ax4.legend(loc=1)

for ax in (ax1, ax2, ax3, ax4):
    ax.grid(True)


process = [None]


def run_client():
    if process[0] is None or process[0].poll() is not None:
        process[0] = subprocess.Popen(
            ["bash", "./client_start.sh"], preexec_fn=os.setsid
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
    else:
        stop_client()


def clear(event):
    _analyzer_unit.input_queue.clear()
    update(True)


def on_close(event):
    print("Figure closed — cleaning up...")
    stop_client()


fig.canvas.mpl_connect("close_event", on_close)
start_button_ax = fig.add_axes([0.8, 0.05, 0.1, 0.075])
start_button = Button(start_button_ax, "Run / Stop)")
start_button.on_clicked(handle_start_button)

clear_button_ax = fig.add_axes([0.7, 0.05, 0.1, 0.075])
clear_button = Button(clear_button_ax, "Clear")
clear_button.on_clicked(clear)


class DataReceiver:
    def __init__(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PULL)
        self.socket.bind("tcp://127.0.0.1:5555")  # binds for incoming PUSH connections

    def update_source(self):
        # ack_buffer = deque(maxlen=3)
        while True:
            try:
                data = self.socket.recv_json(flags=zmq.NOBLOCK)
                # ack_buffer.append(data[2])
                # data.append(sum(ack_buffer) / len(ack_buffer))
                # data.append(data[2])
                _analyzer_unit.input_queue.append(data)
                save_log.append(data)
                time.sleep(0.1)
            except zmq.Again:
                time.sleep(0.1)
                # No message ready
                pass


def update(i):
    _analyzer_unit.update_processing()

    line1.set_data(_analyzer_unit._delta_t, _analyzer_unit._congwin)
    line1c.set_data(_analyzer_unit._delta_t, _analyzer_unit._sent_bytes)
    line2a.set_data(_analyzer_unit._delta_t, _analyzer_unit._raw_acks)
    line2b.set_data(_analyzer_unit._delta_t, _analyzer_unit._filtered_acks)
    line3a.set_data(_analyzer_unit._delta_t, _analyzer_unit._rtts)
    line2c.set_ydata(_analyzer_unit._interpolated_acks)
    """line2d.set_data(_analyzer_unit._delta_t_uniform, _analyzer_unit._detrended_acks)
    line2e.set_data(_analyzer_unit._delta_t_uniform, _analyzer_unit._windowed_acks)"""
    """line3a.set_data(
        np.arange(len(_analyzer_unit._base_to_second_harmonic_ratio)),
        _analyzer_unit._base_to_second_harmonic_ratio,
    )

    line4.set_data(_analyzer_unit._fft_freqs, _analyzer_unit._fft_magnitudes)"""
    crr = _analyzer_unit._congwin_to_response_ratio
    line4.set_data(
        np.arange(len(crr)),
        crr,
    )
    line4b.set_data(
        np.arange(len(_analyzer_unit._loss_rate)),
        np.array(_analyzer_unit._loss_rate) * 10,
    )
    base = _analyzer_unit._base_cwnd
    line1b.set_data(
        _analyzer_unit._delta_t,
        base,
    )
    line2c.set_data(
        _analyzer_unit._delta_t,
        base,
    )

    ax1.relim()
    # ax1.set_ylim(0, 175000)
    ax1.autoscale_view()
    ax3.relim()
    ax3.set_ylim(0, 1.25)
    ax3.autoscale_view()
    ax2.relim()
    # ax2.set_ylim(0, 175000)
    ax2.autoscale_view()
    ax4.relim()
    ax4.set_ylim([0, 2])
    ax4.autoscale_view()


receiver = DataReceiver()
threading.Thread(target=receiver.update_source, daemon=True).start()
ani = animation.FuncAnimation(fig, update, interval=32)
plt.show()
