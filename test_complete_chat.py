"""
Complete test of the chat functionality including web interface simulation
"""
import asyncio
import aiohttp
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_web_interface():
    """Test the web interface components"""
    try:
        print("🌐 Testing Web Interface...")
        print("=" * 40)
        
        async with aiohttp.ClientSession() as session:
            # Test main page
            async with session.get('http://127.0.0.1:8000/chat') as response:
                if response.status == 200:
                    print("✅ Chat page loads successfully")
                    content = await response.text()
                    
                    # Check for key elements
                    if 'agent-select' in content:
                        print("✅ Agent selector found")
                    if 'chat-messages' in content:
                        print("✅ Chat messages container found")
                    if 'chat-input' in content:
                        print("✅ Chat input found")
                    if 'websocket-status' in content:
                        print("✅ WebSocket status indicator found")
                else:
                    print(f"❌ Chat page failed: {response.status}")
                    return False
            
            # Test agents API
            async with session.get('http://127.0.0.1:8000/api/v1/') as response:
                if response.status == 200:
                    agents_data = await response.json()
                    agent_count = len(agents_data.get('agents', []))
                    print(f"✅ {agent_count} agents available")
                    
                    if agent_count > 0:
                        first_agent = agents_data['agents'][0]
                        print(f"✅ First agent: {first_agent['name']} ({first_agent['id']})")
                    else:
                        print("❌ No agents available")
                        return False
                else:
                    print(f"❌ Agents API failed: {response.status}")
                    return False
            
            # Test health page
            async with session.get('http://127.0.0.1:8000/health') as response:
                if response.status == 200:
                    print("✅ Health page loads successfully")
                else:
                    print(f"❌ Health page failed: {response.status}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error testing web interface: {e}")
        return False

async def test_chat_api():
    """Test the chat API endpoints"""
    try:
        print("\n💬 Testing Chat API...")
        print("=" * 30)
        
        async with aiohttp.ClientSession() as session:
            # Test agents endpoint
            async with session.get('http://127.0.0.1:8000/api/v1/') as response:
                agents_data = await response.json()
                agents = agents_data.get('agents', [])
                
                if not agents:
                    print("❌ No agents available for chat test")
                    return False
                
                # Use first agent for testing
                test_agent = agents[0]
                agent_id = test_agent['id']
                print(f"🤖 Using agent: {test_agent['name']} ({agent_id})")
            
            # Test chat endpoint
            chat_data = {
                "message": "Olá, este é um teste do sistema de chat!",
                "agent_id": agent_id
            }
            
            async with session.post(
                'http://127.0.0.1:8000/api/v1/chat',
                json=chat_data
            ) as response:
                if response.status == 200:
                    chat_response = await response.json()
                    print(f"✅ Chat API response: {chat_response.get('message', 'No message')}")
                    print(f"   Agent: {chat_response.get('agent_id', 'Unknown')}")
                    print(f"   Final: {chat_response.get('is_final', 'Unknown')}")
                    return True
                else:
                    print(f"❌ Chat API failed: {response.status}")
                    text = await response.text()
                    print(f"   Error: {text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Error testing chat API: {e}")
        return False

async def test_websocket_connection():
    """Test WebSocket connection"""
    try:
        print("\n🔌 Testing WebSocket Connection...")
        print("=" * 35)
        
        import websockets
        
        # Get available agents first
        async with aiohttp.ClientSession() as session:
            async with session.get('http://127.0.0.1:8000/api/v1/') as response:
                agents_data = await response.json()
                agents = agents_data.get('agents', [])
                
                if not agents:
                    print("❌ No agents available for WebSocket test")
                    return False
                
                test_agent = agents[0]
                agent_id = test_agent['id']
        
        # Test WebSocket connection
        uri = f"ws://127.0.0.1:8000/api/v1/ws/{agent_id}"
        print(f"📡 Connecting to: {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connected")
            
            # Send test message
            test_message = "Teste de conexão WebSocket"
            await websocket.send(test_message)
            print(f"📤 Sent: {test_message}")
            
            # Receive response
            response = await websocket.recv()
            print(f"📥 Received: {response}")
            
            # Try to parse JSON
            try:
                response_data = json.loads(response)
                print(f"✅ Response parsed: {response_data.get('message', 'No message')}")
            except json.JSONDecodeError:
                print(f"✅ Raw response: {response}")
            
            return True
            
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False

async def simulate_user_workflow():
    """Simulate complete user workflow"""
    try:
        print("\n👤 Simulating User Workflow...")
        print("=" * 35)
        
        print("1. User opens browser and navigates to chat page")
        print("2. User sees 3 available agents")
        print("3. User selects 'Agente de Demonstração 1'")
        print("4. User types: 'Olá, como você pode me ajudar?'")
        print("5. System processes message via WebSocket")
        print("6. Agent responds (echo or LLM response)")
        print("7. User continues conversation...")
        
        # Simulate multiple messages
        messages = [
            "Olá, como você pode me ajudar?",
            "Quais são os recursos do sistema?",
            "Pode me monitorar jobs?",
            "Obrigado!"
        ]
        
        print(f"\n💬 Simulating {len(messages)} messages...")
        
        import websockets
        
        # Get first agent
        async with aiohttp.ClientSession() as session:
            async with session.get('http://127.0.0.1:8000/api/v1/') as response:
                agents_data = await response.json()
                agent_id = agents_data['agents'][0]['id']
        
        uri = f"ws://127.0.0.1:8000/api/v1/ws/{agent_id}"
        
        async with websockets.connect(uri) as websocket:
            for i, message in enumerate(messages, 1):
                print(f"\n  Message {i}/{len(messages)}")
                print(f"  User: {message}")
                
                await websocket.send(message)
                response = await websocket.recv()
                
                try:
                    response_data = json.loads(response)
                    agent_msg = response_data.get('message', 'No response')
                    print(f"  Agent: {agent_msg[:50]}{'...' if len(agent_msg) > 50 else ''}")
                except:
                    print(f"  Agent: {response}")
                
                await asyncio.sleep(0.5)  # Small delay between messages
        
        print("\n✅ User workflow simulation completed!")
        return True
        
    except Exception as e:
        print(f"❌ Workflow simulation failed: {e}")
        return False

async def main():
    """Main test function"""
    print("🧪 Complete Chat Test Suite")
    print("=" * 50)
    
    # Test all components
    tests = [
        ("Web Interface", test_web_interface),
        ("Chat API", test_chat_api),
        ("WebSocket", test_websocket_connection),
        ("User Workflow", simulate_user_workflow)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*50}")
    print("📊 TEST SUMMARY")
    print(f"{'='*50}")
    
    passed = sum(1 for name, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Chat system is fully functional!")
        print("\n🌐 You can now use the chat system at: http://127.0.0.1:8000/chat")
        print("💬 Features available:")
        print("  - Web interface with agent selection")
        print("  - Real-time WebSocket chat")
        print("  - API endpoints for integration")
        print("  - Multiple AI agents")
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the configuration.")

if __name__ == "__main__":
    asyncio.run(main())
