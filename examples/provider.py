# provider.py
import asyncio

async def generate_data(queue):
    for i in range(5):
        message = f"Message {i}"
        print(f"[provider] Sending: {message}")
        await queue.put(message)
        await asyncio.sleep(1)  # Simulate some delay in data generation

    # Signal the client to stop by sending a None
    await queue.put(None)

async def main():
    queue = asyncio.Queue()

    # Start generating data in the provider
    await generate_data(queue)

if __name__ == "__main__":
    asyncio.run(main())
