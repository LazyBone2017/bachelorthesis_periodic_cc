# Simulating a provider feeding data to the queue
import asyncio

"""
    Simulates an application providing data to the protocol.
    Pushes dummy data into the queue at [data_rate] MB/s.

    For iterations=0, the provider keeps generating data indefinitely
"""


async def provider(queue, data_rate=1, iterations=1):
    chunk_size = data_rate * 1024 * 1024
    counter = 0

    while True:
        data = f"Data {counter}".ljust(chunk_size, "X")
        await queue.put(data)
        print(f"[provider] Pushed: Data {counter} ({len(data)} bytes)")

        counter += 1
        if (
            counter > iterations and iterations != 0
        ):  # iterations == 0 keeps the loop active
            break
        await asyncio.sleep(1)

    await queue.put(None)
