import asyncio
import csv
import os
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import HandshakeCompleted
from aioquic.asyncio import QuicConnectionProtocol
from aioquic.quic.congestion.periodic import PKT_TRANSPORT_LOG
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np


class ClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            print("[client] Handshake completed successfully.")

    async def send_data(self, data):
        stream_id = self._quic.get_next_available_stream_id()
        self._quic.send_stream_data(stream_id, data.encode(), end_stream=False)
        self.transmit()
        print(f"[client] Sent data: {len(data)} Bytes")


def save_to_csv(filename, data, fieldnames):
    with open(filename, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)

def condense(log, period):
    cutoff = log[0][1] + period
    rate_log = []
    pkt_count_s = 0
    pkt_count_a = 0
    n = 0
    for i in log:
        if(i[1] >= cutoff):
            cutoff += period
            rate_log.append([n, pkt_count_s, pkt_count_a, i[3]])
            n += 1
            pkt_count_a = 1
            pkt_count_s = 1
        if(i[0] == "ACK"):
            pkt_count_a += 1
        else: pkt_count_s += 1
    return rate_log



class QuicClient:
    def __init__(self, host, port, queue):
        self.host = host
        self.port = port
        self.queue = queue
        self.configuration = QuicConfiguration(is_client=True, alpn_protocols=["hq-29"], congestion_control_algorithm="periodic")  # QUIC with HTTP/3
        self.configuration.verify_mode = False  # Disable certificate verification for testing
        self.configuration.secrets_log_file=open("secrets.log", "a");

    async def run(self):
        # Establish the QUIC connection
        async with connect(self.host, self.port, configuration=self.configuration, create_protocol=ClientProtocol) as connection:
            print("[client] Connected to server.")
            
            # Send data from the queue to the server
            while True:

                data = await self.queue.get()
                if data is None:
                    print("[client] Provider stopped data stream, closing stream.")
                    # Gracefully disconnect when no more data is available
                    connection._quic.send_stream_data(0, b'', end_stream=True)  # Close the stream
                    connection.transmit();
                    break  # Exit the loop after sending the disconnect signal
                await connection.send_data(data)
                await asyncio.sleep(0)  # Let the event loop process other tasks

            # Disconnect the QUIC connection when done
            print("All done. Connection is being closed...")
            connection.close()
            await connection.wait_closed()
            rate_log = condense(PKT_TRANSPORT_LOG, 0.1)
            save_to_csv("packet_rate.csv", rate_log, ["TYPE", "PACKET_NUM", "TIME"])
            save_to_csv("packet_log.csv", PKT_TRANSPORT_LOG, ["TYPE", "PACKET_NUM", "TIME"])
            plot_graph(rate_log)
            print("Client Shutdown.")

async def main():
    queue = asyncio.Queue()

    # Simulating a provider feeding data to the queue
    async def provider(queue, data_rate=1):
        chunk_size = data_rate * 1024 * 1024  #[data_rate] MB in bytes
        counter = 0

        while True:
            # Generate [data_rate] MB of dummy data (you can replace this with real data)
            data = f"Data {counter}".ljust(chunk_size, 'X')  # Create a string of size 2 MB
            await queue.put(data)
            print(f"[provider] Pushed: Data {counter} ({len(data)} bytes)")

            counter += 1
            if(counter >= 30): break
            await asyncio.sleep(1)  # Sleep for 1 second to maintain the rate of 2 MB/s

        # Signal that the provider is done when it finishes
        await queue.put(None)

    

    # Start the client and provider tasks
    client = QuicClient('localhost', 4433, queue) 
    provider_task = asyncio.create_task(provider(queue, data_rate=1))
    
    client_task = asyncio.create_task(client.run())

    # Wait for both tasks to finish
    await asyncio.gather( provider_task, client_task)


def plot_graph(data):
    x = [v[0] for v in data]
    y = [v[1] for v in data]
    z = [v[2] for v in data]
    c = [v[3] / 1000 for v in data]

    fig, ax = plt.subplots()
    ax.plot(x, y)
    ax.plot(x, z)
    ax.plot(x, c)
    ax.set_title("Sine Wave")

    ax.set_title("Graph from Points")
    ax.set_xlabel("Time(s)")
    ax.set_ylabel("n packets")

    window = tk.Tk()
    window.title("Graph Viewer")
    window.geometry("1920x1080")

    canvas = FigureCanvasTkAgg(fig, master=window)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def on_closing():
        window.destroy()
        window.quit()

    
    window.protocol("WM_DELETE_WINDOW", on_closing)

    window.mainloop()

if __name__ == "__main__":
    asyncio.run(main())
