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
    single_file_mode = configuration["provider"]["single_file_mode"]
    chunk_size = rate * int(125000 / subchunks)
    counter = 0
    payload = "Data".ljust(chunk_size, "X")

    if single_file_mode:
        filesize = int(configuration["provider"]["single_file_size_mbit"])
        marker = "!"
        payload_size = filesize * 125000
        queue.put_nowait("?".ljust(payload_size - len(marker), "X") + marker)
        return

    while True:
        queue.put_nowait(payload)
        # print(f"[provider] Pushed: Data {counter} ({len(payload)} bytes)", flush=True)

        counter += 1 / subchunks
        if counter >= iterations:
            print("Finished")
            break
        await asyncio.sleep(1 / subchunks)

    await queue.put(None)
