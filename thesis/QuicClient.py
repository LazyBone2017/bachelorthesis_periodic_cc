import asyncio
from aioquic.asyncio.client import connect
from aioquic.quic.configuration import QuicConfiguration
from ClientProtocol import ClientProtocol


class QuicClient:
    def __init__(self, host, port, queue):
        self.host = host
        self.port = port
        self.queue = queue
        self.configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=["hq-29"],
            congestion_control_algorithm="periodic",
        )
        self.configuration.verify_mode = False
        self.configuration.secrets_log_file = open("secrets.log", "a")

    async def run(self):
        async with connect(
            self.host,
            self.port,
            configuration=self.configuration,
            create_protocol=ClientProtocol,
        ) as connection:
            print("[client] Connected to server.")
            while True:

                data = await self.queue.get()
                if data is None:
                    print("[client] Provider stopped data stream, closing stream.")
                    connection._quic.send_stream_data(0, b"", end_stream=True)
                    connection.transmit()
                    break
                await connection.send_data(data)
                await asyncio.sleep(0)

            print("All done. Connection is being closed...")

            connection.close()
            await connection.wait_closed()

            print("Client Shutdown.")
