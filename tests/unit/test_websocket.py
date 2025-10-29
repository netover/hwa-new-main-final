import asyncio
import json

import websockets


async def test_websocket():
    uri = "ws://127.0.0.1:8000/api/v1/ws/test-agent"
    try:
        print(f"Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")

            # Send a test message
            test_message = {
                "type": "chat_message",
                "content": "Hello WebSocket!"
            }
            await websocket.send(json.dumps(test_message))
            print("Message sent:", test_message)

            # Receive response
            response = await websocket.recv()
            print("Response received:", response)

            # Try to parse response
            try:
                response_data = json.loads(response)
                print("Parsed response:", response_data)
            except json.JSONDecodeError:
                print("Response is not valid JSON")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
