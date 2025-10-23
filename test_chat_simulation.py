"""
Test script to simulate a complete conversation on /chat endpoint
"""
import asyncio
import websockets
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def simulate_chat_conversation():
    """Simulate a complete chat conversation"""
    try:
        print("🤖 Simulating Chat Conversation...")
        print("=" * 50)
        
        # Connect to WebSocket
        uri = "ws://127.0.0.1:8000/api/v1/ws/demo-agent-1"
        print(f"📡 Connecting to: {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket")
            
            # Simulate conversation messages
            messages = [
                "Olá! Como você está?",
                "O que você pode fazer no sistema Resync?",
                "Pode me ajudar a monitorar jobs do TWS?",
                "Quais são os principais recursos disponíveis?",
                "Obrigado pela ajuda!"
            ]
            
            print(f"\n💬 Starting conversation with {len(messages)} messages...")
            
            for i, message in enumerate(messages, 1):
                print(f"\n--- Message {i}/{len(messages)} ---")
                print(f"User: {message}")
                
                # Send message
                await websocket.send(message)
                
                # Wait for response
                response = await websocket.recv()
                response_data = json.loads(response)
                
                print(f"Agent: {response_data.get('message', 'No response')}")
                
                # Small delay between messages
                await asyncio.sleep(1)
            
            print("\n✅ Conversation completed successfully!")
            return True
            
    except Exception as e:
        print(f"❌ Error during chat simulation: {e}")
        return False

async def test_agent_selection():
    """Test agent selection first"""
    try:
        import aiohttp
        
        print("\n🔍 Testing Agent Selection...")
        print("=" * 30)
        
        async with aiohttp.ClientSession() as session:
            # Get available agents
            async with session.get('http://127.0.0.1:8000/api/v1/') as response:
                agents_data = await response.json()
                
            print("Available agents:")
            for agent in agents_data.get('agents', []):
                print(f"  - {agent['id']}: {agent['name']} ({agent['status']})")
            
            if agents_data.get('agents'):
                selected_agent = agents_data['agents'][0]['id']
                print(f"\n✅ Selected agent: {selected_agent}")
                return selected_agent
            else:
                print("❌ No agents available")
                return None
                
    except Exception as e:
        print(f"❌ Error testing agent selection: {e}")
        return None

async def main():
    """Main test function"""
    print("🧪 Chat Simulation Test Suite")
    print("=" * 50)
    
    # Test agent selection
    agent_id = await test_agent_selection()
    
    if agent_id:
        # Test chat conversation
        success = await simulate_chat_conversation()
        
        if success:
            print("\n🎯 Chat simulation completed successfully!")
            print("\n📊 Summary:")
            print("✅ Agent selection: Working")
            print("✅ WebSocket connection: Working")
            print("✅ Message exchange: Working")
            print("✅ Response handling: Working")
        else:
            print("\n❌ Chat simulation failed.")
    else:
        print("\n❌ Cannot proceed with chat simulation - no agents available.")

if __name__ == "__main__":
    asyncio.run(main())
