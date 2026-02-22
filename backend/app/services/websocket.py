import json
from fastapi import WebSocket


class WSManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict, exclude: WebSocket | None = None):
        """Рассылка JSON-сообщения всем, кроме `exclude`."""
        txt = json.dumps(message, ensure_ascii=False)
        for connection in self.active_connections:
            if connection == exclude:
                continue
            try:
                await connection.send_text(txt)
            except Exception:
                # Если соединение разорвано, удалим
                # (но обычно disconnect вызывается раньше)
                pass

ws_manager = WSManager()
