import asyncio
from collections import deque
import queue
import threading
import time
from matplotlib import pyplot as plt
from matplotlib import animation
from matplotlib.animation import FuncAnimation
from matplotlib.mlab import detrend
import numpy as np
import scipy
import zmq

counter = 0

fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1)
(line1,) = ax1.plot([], [], label="CongWin")
(line2a,) = ax2.plot([], [], label="Acked Bytes")
(line2b,) = ax2.plot([], [], label="Acked Bytes Interpolated", color="red")
(line2c,) = ax2.plot([], [], label="Acked Bytes Interpolated Demeaned", color="green")
(line2d,) = ax2.plot([], [], label="Acked Bytes Interpolated Detrended", color="orange")
(line3,) = ax3.plot([], [], label="RTT")
(line4,) = ax4.plot([], [], label="Frequency Distribution")


ax1.set_ylabel("CongWin")
ax2.set_ylabel("Acked")
ax3.set_ylabel("RTT")
ax3.set_xlabel("Time (s)")


for ax in (ax1, ax2, ax3):
    ax.legend()
    ax.grid(True)


data_queue = deque(maxlen=1000)
save_log = []


class DataReceiver:
    def __init__(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PULL)
        self.socket.bind("tcp://127.0.0.1:5555")  # binds for incoming PUSH connections

    def update_source(self):
        ack_buffer = deque(maxlen=10)
        while True:
            try:
                data = self.socket.recv_json(flags=zmq.NOBLOCK)
                ack_buffer.append(data[2])
                data.append(sum(ack_buffer) / len(ack_buffer))
                data_queue.append(data)
                save_log.append(data)
                time.sleep(0.1)
            except zmq.Again:
                time.sleep(0.1)
                # No message ready
                pass


def update(i):
    if len(data_queue) == 0:
        return

    timestamps, congwin, acks_per_interval, latest_rtt, smoothed_acks_per_interval = (
        zip(*data_queue)
    )

    # timestamps_uniform = np.linspace(timestamps[0], timestamps[-1], 100)
    timestamps_uniform = np.arange(timestamps[0], timestamps[-1], 0.75)
    interp_acks_per_interval = np.interp(
        timestamps_uniform, timestamps, smoothed_acks_per_interval
    )

    """signal = acks_per_interval_uniform - np.mean(acks_per_interval_uniform)
    signal = detrend(
        signal, "linear", axis=0
    )"""  # important, has to be connected to linear increase mode
    if len(interp_acks_per_interval) != 0:
        interp_acks_per_interval_demeaned = interp_acks_per_interval - np.mean(
            interp_acks_per_interval
        )
        interp_acks_per_interval_detrended = detrend(
            interp_acks_per_interval, "linear", axis=0
        )
        fft = np.fft.rfft(interp_acks_per_interval)
        freqs = np.fft.rfftfreq(len(interp_acks_per_interval), d=0.75)

        line2c.set_data(timestamps_uniform, interp_acks_per_interval_demeaned)
        line2d.set_data(timestamps_uniform, interp_acks_per_interval_detrended)
        line4.set_data(freqs[freqs > 0], np.abs(fft[freqs > 0]))

    line1.set_data(timestamps, congwin)
    line2a.set_data(timestamps, acks_per_interval)
    line2b.set_data(timestamps_uniform, interp_acks_per_interval)
    line3.set_data(timestamps, latest_rtt)
    ax1.relim()
    ax1.autoscale_view()
    ax2.relim()
    ax2.autoscale_view()
    ax3.relim()
    ax3.autoscale_view()
    ax4.relim()
    ax4.autoscale_view()


receiver = DataReceiver()
threading.Thread(target=receiver.update_source, daemon=True).start()
ani = animation.FuncAnimation(fig, update, interval=32)
plt.show()
