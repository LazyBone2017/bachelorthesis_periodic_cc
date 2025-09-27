# Simulating a provider feeding data to the queue
import asyncio

"""
    Simulates an application providing data to the protocol.
    Pushes dummy data into the queue at [rate_mbit] mbit/s.
"""


async def provider(queue, configuration):
    rate = int(configuration["provider"]["rate_mbit"])
    subchunks = int(configuration["provider"]["granularity"])
    iterations = int(configuration["provider"]["iterations"])
    chunk_size = rate * int(1000000 / subchunks)
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
