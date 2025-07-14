from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.events import HandshakeCompleted


class ClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            print("[client] Handshake completed successfully.")

    async def send_data(self, data):
        stream_id = self._quic.get_next_available_stream_id()
        self._quic.send_stream_data(stream_id, data.encode(), end_stream=False)
        self.transmit()
        # print(f"[client] Sent data: {len(data)} Bytes")
