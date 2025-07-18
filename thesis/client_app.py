import asyncio
import csv
import os
import threading

import nicegui

from QuicClient import QuicClient
from aioquic.quic.congestion.periodic import LOG
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import make_splrep, splev
from nicegui import ui

from data_provider import provider


async def main():
    send_data_queue = asyncio.Queue()

    # Start the client and provider tasks
    client = QuicClient("10.0.0.2", 4433, send_data_queue)

    provider_task = asyncio.create_task(
        provider(send_data_queue, data_rate=10, iterations=5000)
    )
    client_task = asyncio.create_task(client.run())
    """thread = threading.Thread(
        target=client.run(on_connection_close_callback=plot_graph()), daemon=True
    )
    await thread.run()"""
    # Wait for both tasks to finish
    await asyncio.gather(provider_task, client_task)


if __name__ in {"__main__", "__mp_main__"}:
    asyncio.run(main())
