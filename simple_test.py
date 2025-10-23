import asyncio
import websockets


async def simple_test():
    print("Starting WebSocket test...")
    try:
        uri = "ws://localhost:8030/api/v1/ws/tws-general"
        print(f"Connecting to {uri}...")

        # Connect with timeout
        websocket = await asyncio.wait_for(websockets.connect(uri), timeout=10.0)
        print("Connected successfully!")

        # Get welcome message with timeout
        print("Waiting for welcome message...")
        welcome = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        print(f"Welcome message: {welcome}")

        await websocket.close()
        print("Test completed successfully!")

    except asyncio.TimeoutError:
        print("Test failed: Timeout (10 seconds)")
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(simple_test())
