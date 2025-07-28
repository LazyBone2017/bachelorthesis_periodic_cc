# Simulating a provider feeding data to the queue
import asyncio

"""
    Simulates an application providing data to the protocol.
    Pushes dummy data into the queue at [data_rate] MB/s.
"""


async def provider(queue, data_rate, iterations, subchunks):
    chunk_size = data_rate * int(125000 / subchunks)
    counter = 0
    payload = "Data".ljust(chunk_size, "X")

    while True:
        queue.put_nowait(payload)
        # print(f"[provider] Pushed: Data {counter} ({len(payload)} bytes)", flush=True)

        counter += 1 / subchunks
        if counter >= iterations:
            print("Finished")
            break
        await asyncio.sleep(1 / subchunks)

    await queue.put(None)
