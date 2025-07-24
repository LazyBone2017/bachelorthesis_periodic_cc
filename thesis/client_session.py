import asyncio
import QuicClient
from data_provider import provider


async def main():
    send_data_queue = asyncio.Queue()
    data_rate = 10
    chunk_size = data_rate * 131072
    payload = "Data".ljust(chunk_size, "X")
    for i in range(100):
        send_data_queue.put_nowait(payload)

    # Start the client and provider tasks
    client = QuicClient.QuicClient("10.0.0.2", 4433, send_data_queue)

    """provider_task = asyncio.create_task(
        provider(send_data_queue, data_rate=30, iterations=5000)
    )"""
    client_task = asyncio.create_task(client.run())
    """thread = threading.Thread(
        target=client.run(on_connection_close_callback=plot_graph()), daemon=True
    )
    await thread.run()"""
    # Wait for both tasks to finish
    await asyncio.gather(client_task)


if __name__ in {"__main__", "__mp_main__"}:
    asyncio.run(main())
