# Simulating a provider feeding data to the queue
import asyncio

"""
    Simulates an application providing data to the protocol.
    Pushes dummy data into the queue at [data_rate] MB/s.
"""


async def provider(queue, data_rate=1, iterations=1):
    chunk_size = data_rate * 131072
    counter = 0
    payload = "Data".ljust(chunk_size, "X")

    while True:
        await queue.put(payload)
        # print(f"[provider] Pushed: Data {counter} ({len(payload)} bytes)")

        counter += 1
        if counter > iterations:
            print("Finished")
            break
        await asyncio.sleep(1)

    await queue.put(None)
