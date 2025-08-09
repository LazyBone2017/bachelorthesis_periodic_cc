import asyncio
import QuicClient
from data_provider import provider


async def main():
    send_data_queue = asyncio.Queue()

    # Start the client and provider tasks
    client = QuicClient.QuicClient("10.0.0.2", 4433, send_data_queue)

    provider_task = asyncio.create_task(
        provider(send_data_queue, data_rate=20, iterations=650, subchunks=100)
    )
    client_task = asyncio.create_task(client.run())

    client_task.add_done_callback(
        lambda t: print("TASK FINISHED:", t, "EXCEPTION:", t.exception())
    )

    # Wait for both tasks to finish
    await asyncio.gather(provider_task, client_task)
    print("Main task stopped")


if __name__ in {"__main__", "__mp_main__"}:
    asyncio.run(main())
