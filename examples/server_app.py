# server.py
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.events import StreamDataReceived

class EchoProtocol(QuicConnectionProtocol):
    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            print(f"[server] Received data: {event.data.decode()}")
            # Echo the data back to the sender
            self._quic.send_stream_data(event.stream_id, event.data, end_stream=True)
            self.transmit()

# Start the server and listen for connections
async def main():
    config = QuicConfiguration(is_client=False, alpn_protocols=["hq-29"])
    config.load_cert_chain(certfile="../tests/ssl_cert.pem", keyfile="../tests/ssl_key.pem")

    # Listen for incoming QUIC connections on port 4433
    server = await serve("localhost", 4433, configuration=config, create_protocol=EchoProtocol)

    
    await asyncio.Future()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
