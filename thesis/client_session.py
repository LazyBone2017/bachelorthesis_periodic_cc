import asyncio
import tomllib
import QuicClient
from data_provider import provider


async def main():

    send_data_queue = asyncio.Queue()

    config = None
    with open("config_periodic.toml", "rb") as f:
        config = tomllib.load(f)
        print("config read: ", config)

    # Start the client and provider tasks

    client = QuicClient.QuicClient(
        "10.0.0.2", 4433, send_data_queue, external_config=config
    )

    provider_task = asyncio.create_task(
        provider(send_data_queue, data_rate=30, iterations=650, subchunks=1000)
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
