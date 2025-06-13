from collections import deque
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.mlab import detrend
import numpy as np
import scipy
import zmq

context = zmq.Context()
socket = context.socket(zmq.PULL)
socket.bind("tcp://127.0.0.1:5555")  # binds for incoming PUSH connections

maxlen = 1000
timestamps = deque(maxlen=maxlen)
congwin = deque(maxlen=maxlen)
acks_per_interval = deque(maxlen=maxlen)
latest_rtt = deque(maxlen=maxlen)

fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1)
(line1,) = ax1.plot([], [], label="CongWin")
(line2a,) = ax2.plot([], [], label="Acked Bytes")
(line2b,) = ax2.plot([], [], label="Acked Bytes Interpolated", color="red")
(line3,) = ax3.plot([], [], label="RTT")
(line4,) = ax4.plot([], [], label="Frequency Distribution")


ax1.set_ylabel("CongWin")
ax2.set_ylabel("Acked")
ax3.set_ylabel("RTT")
ax3.set_xlabel("Time (s)")


for ax in (ax1, ax2, ax3):
    ax.legend()
    ax.grid(True)


def update_source():
    try:
        data = socket.recv_json(flags=zmq.NOBLOCK)
        timestamps.append(data[0])
        congwin.append(data[1])
        acks_per_interval.append(data[2])
        latest_rtt.append(data[3])
    except zmq.Again:
        # No message ready
        pass


def update(frame):
    update_source()
    if not timestamps or len(timestamps) == 0:
        return

    timestamps_uniform = np.arange(timestamps[0], timestamps[-1], 0.1)
    interpolated_fn = scipy.interpolate.interp1d(
        timestamps, acks_per_interval, kind="linear", fill_value="extrapolate"
    )
    acks_per_interval_uniform = interpolated_fn(timestamps_uniform)

    """signal = acks_per_interval_uniform - np.mean(acks_per_interval_uniform)
    signal = detrend(
        signal, "linear", axis=0
    )  """  # important, has to be connected to linear increase mode

    # fft = np.fft.rfft(signal)
    # freqs = np.fft.rfftfreq(len(signal), d=0.1)

    line1.set_data(timestamps, congwin)
    line2a.set_data(timestamps, acks_per_interval)
    line2b.set_data(timestamps_uniform, acks_per_interval_uniform)
    line3.set_data(timestamps, latest_rtt)
    # line4.set_data(freqs[freqs > 0], np.abs(fft[freqs > 0]))
    ax1.relim()
    ax1.autoscale_view()
    ax2.relim()
    ax2.autoscale_view()
    ax3.relim()
    ax3.autoscale_view()
    ax4.relim()
    ax4.autoscale_view()


ani = FuncAnimation(fig, update, interval=50)  # 50ms ≈ 20fps
plt.tight_layout()
plt.show()
