import asyncio
import time
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import QuicClient
import argparse
from data_provider import provider


async def main():

    send_data_queue = asyncio.Queue()

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = None
    with open(args.config, "rb") as f:
        config = tomllib.load(f)
        print("config read: ", config)

    # Start the client and provider tasks
    client = QuicClient.QuicClient(
        "10.0.0.2", 4433, send_data_queue, external_config=config
    )

    provider_task = asyncio.create_task(provider(send_data_queue, configuration=config))
    client_task = asyncio.create_task(client.run())

    client_task.add_done_callback(
        lambda t: print("TASK FINISHED:", t, "EXCEPTION:", t.exception())
    )

    # Wait for both tasks to finish
    await asyncio.gather(provider_task, client_task)
    print("Main task stopped")


if __name__ in {"__main__", "__mp_main__"}:
    asyncio.run(main())
