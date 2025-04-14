import asyncio
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import HandshakeCompleted
from aioquic.asyncio import QuicConnectionProtocol

class ClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            print("[client] Handshake completed successfully.")

    async def send_data(self, data):
        stream_id = self._quic.get_next_available_stream_id()
        self._quic.send_stream_data(stream_id, data.encode(), end_stream=True)
        self.transmit()
        print(f"[client] Sent data: {data}")

class QuicClient:
    def __init__(self, host, port, queue):
        self.host = host
        self.port = port
        self.queue = queue
        self.configuration = QuicConfiguration(is_client=True, alpn_protocols=["hq-29"])  # QUIC with HTTP/3
        self.configuration.verify_mode = False  # Disable certificate verification for testing
        self.configuration.secrets_log_file=open("secrets.log", "a");

    async def run(self):
        # Establish the QUIC connection
        async with connect(self.host, self.port, configuration=self.configuration, create_protocol=ClientProtocol) as connection:
            print("[client] Connected to server.")
            
            # Send data from the queue to the server
            while True:
                print("test")
                data = await self.queue.get()
                if data is None:
                    # Gracefully disconnect when no more data is available
                    connection._quic.send_stream_data(0, b'', end_stream=True)  # Close the stream
                    break  # Exit the loop after sending the disconnect signal
                await connection.send_data(data)
                await asyncio.sleep(0)  # Let the event loop process other tasks

            # Disconnect the QUIC connection when done
            await connection.close()

async def main():
    queue = asyncio.Queue()

    # Simulating a provider feeding data to the queue
    async def provider(queue, data_rate=2):
        chunk_size = 2 * 1024 * 1024  # 2 MB in bytes
        counter = 0

        while True:
            # Generate 2 MB of dummy data (you can replace this with real data)
            data = f"Data {counter}".ljust(chunk_size, 'X')  # Create a string of size 2 MB
            await queue.put(data)
            print(f"[provider] Pushed: Data {counter} ({len(data)} bytes)")

            counter += 1
            await asyncio.sleep(1)  # Sleep for 1 second to maintain the rate of 2 MB/s

    # Signal that the provider is done when it finishes
    await queue.put(None)

    # Start the client and provider tasks
    client = QuicClient('localhost', 4433, queue) 
    #provider_task = asyncio.create_task(provider(queue, data_rate=2))
    
    client_task = asyncio.create_task(client.run())

    # Wait for both tasks to finish
    await asyncio.gather(client_task)

if __name__ == "__main__":
    asyncio.run(main())
