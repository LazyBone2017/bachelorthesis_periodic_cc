import asyncio
from collections import deque
import threading
import time
from matplotlib import pyplot as plt
from matplotlib.widgets import TextBox
import matplotlib
from nicegui import ui


class DiagnosticsMonitor:
    def __init__(self, modulationAnalyzer):
        self.modulationAnalyzer = modulationAnalyzer
        self.diagnostics_queue = deque(maxlen=100)
        # asyncio.create_task(self.init_ui())
        # matplotlib.interactive(True)

    async def init_ui(self):
        # amplitude chart, frequency chart
        fig, (self.ax_time, self.ax_freq, self.ax_shift) = plt.subplots(
            1, 3, figsize=(10, 4)
        )  # 1 row, 2 columns
        """self.timestamp_queue.append(
              DiagnosticsMonitor  (time.monotonic(), self.bytes_in_flight, self.congestion_window)
            )
            timestamps, in_flight, congwin = zip(*self.timestamp_queue)

            """  # amplitude graph
        (self.line_amplitude_in_flight,) = self.ax_time.plot(
            [], [], "r-"
        )  # Red line for in_flight

        (self.line_amplitude_congwin,) = self.ax_time.plot(
            [], [], "g-"
        )  # green line for congwin

        # frequency graph
        (self.line_freq,) = self.ax_freq.plot([], [], "b-")

        (self.line_shift,) = self.ax_shift.plot([], [], "o-")

        self.ax_time.set_ylim(90000, 110000)

        axbox = plt.axes([0.25, 0.05, 0.5, 0.05])
        self.textbox = TextBox(
            axbox,
            "Frequency:",
            initial=str(self.modulationAnalyzer.modulation_frequency),
        )
        self.textbox.on_submit(
            lambda text: setattr(
                self.modulationAnalyzer, "modulation_frequency", float(text)
            )
        )
        update_thread = threading.Thread(target=self.update_ui, daemon=True)

        # update_thread.start()

    def update_ui(self):
        while True:
            print("RT")
            if len(self.diagnostics_queue) > 0:
                timestamps, congwin, in_flight = zip(*self.diagnostics_queue)
                self.line_amplitude_in_flight.set_xdata(timestamps)  # set data
                self.line_amplitude_in_flight.set_ydata(in_flight)  # set data
                self.line_amplitude_congwin.set_xdata(timestamps)  # set data
                self.line_amplitude_congwin.set_ydata(congwin)  # set data
                self.ax_time.relim()
                self.ax_time.autoscale_view()

                # maybe replace with normal conditional
                """
                self.line_freq.set_xdata(freqs)
                self.line_freq.set_ydata(np.abs(fft))
                self.ax_freq.relim()
                self.ax_freq.autoscale_view()"""

                plt.show()
                plt.pause(0.01)
            time.sleep(0.1)
