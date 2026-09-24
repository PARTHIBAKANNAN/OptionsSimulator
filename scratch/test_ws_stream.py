import asyncio, json, sys
import websockets
sys.path.insert(0, '/home/ubuntu/optionssimulator-app')
from backend.app.config import WebConfig
import jwt

async def main():
    cfg = WebConfig.load()
    token = jwt.encode({'sub': 'test-user', 'email': 'test@example.com', 'aud': 'authenticated'}, cfg.supabase_jwt_secret, algorithm='HS256')
    uri = f'ws://127.0.0.1:8001/ws/stream?token={token}'
    async with websockets.connect(uri) as ws:
        snap = await ws.recv()
        print('RECEIVED SNAPSHOT, bytes:', len(snap))
        for i in range(5):
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(msg)
            frame_type = data.get('type')
            keys = list(data.get('data', {}).keys()) if 'data' in data else []
            print(f'FRAME {i+1} [{frame_type}]: {keys}')

if __name__ == '__main__':
    asyncio.run(main())
