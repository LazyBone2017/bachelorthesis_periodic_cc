import asyncio
import time
from aioquic.asyncio.client import connect
from aioquic.quic.configuration import QuicConfiguration
from ClientProtocol import ClientProtocol

N_STREAMS = 1


class QuicClient:
    def __init__(self, host, port, queue, external_config):
        self.host = host
        self.port = port
        self.queue = queue
        self.configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=["hq-29"],
            congestion_control_algorithm=external_config["cca"]["name"],
            max_datagram_size=1200,
        )
        self.configuration.verify_mode = False
        self.configuration.secrets_log_file = open("secrets.log", "a")
        self.external_config = external_config

    async def run(self):
        async with connect(
            self.host,
            self.port,
            configuration=self.configuration,
            create_protocol=ClientProtocol,
            external_config=self.external_config,
        ) as connection:
            print("[client] Connected to server.")
            print(time.monotonic())
            streams = []
            stream_selected = 0
            for i in range(N_STREAMS):
                reader, writer = await connection.create_stream()
                streams.append(writer)

            while True:
                data = await self.queue.get()
                if data is None:
                    print("[client] Provider stopped data stream, closing stream.")
                    writer.write_eof()
                    break
                streams[stream_selected].write(data.encode())
                await streams[stream_selected].drain()
                stream_selected = (
                    0 if stream_selected == N_STREAMS - 1 else stream_selected + 1
                )
                await asyncio.sleep(0)

            print("[client] Finished. Connection is being closed...")

            connection.close()
            await connection.wait_closed()

            print("[client] Client Shutdown.")
