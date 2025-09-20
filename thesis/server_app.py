# server.py
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.events import StreamDataReceived


class EchoProtocol(QuicConnectionProtocol):
    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            print(f"[server] Received data: {len(event.data)}", flush=True)
            # Echo the data back to the sender
            # self._quic.send_stream_data(event.stream_id, event.data, end_stream=True)
            # self.transmit()


async def main():
    config = QuicConfiguration(
        is_client=False,
        alpn_protocols=["hq-29"],
        congestion_control_algorithm="reno_default",
    )
    config.load_cert_chain(
        certfile="../../tests/ssl_cert.pem", keyfile="../../tests/ssl_key.pem"
    )
    port = 4433
    host = "10.0.0.2"

    print(f"[server] Running on {host}:{port}")
    server = await serve(host, port, configuration=config, create_protocol=EchoProtocol)

    await asyncio.Future()


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[server] Shutdown complete.")
