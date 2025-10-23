"""
Test script for LLM Service
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_llm_service():
    """Test the LLM service"""
    try:
        # Import the LLM service
        from resync.services.llm_service import get_llm_service
        
        print("🧪 Testing LLM Service...")
        print("=" * 50)
        
        # Get LLM service instance
        llm_service = get_llm_service()
        print(f"✅ LLM service initialized with model: {llm_service.model}")
        
        # Test basic response
        print("\n📝 Testing basic response...")
        messages = [
            {"role": "system", "content": "Você é um assistente útil que responde em português."},
            {"role": "user", "content": "Olá! Como está o sistema Resync?"}
        ]
        
        response = await llm_service.generate_response(messages, max_tokens=100)
        print(f"✅ Response received: {response}")
        
        # Test health check
        print("\n🏥 Testing health check...")
        health_status = await llm_service.health_check()
        print(f"✅ Health status: {health_status['status']}")
        print(f"   Model: {health_status['model']}")
        print(f"   Endpoint: {health_status['endpoint']}")
        
        # Test agent response
        print("\n🤖 Testing agent response...")
        agent_response = await llm_service.generate_agent_response(
            agent_id="test-agent",
            user_message="Quais são os principais recursos do sistema?",
            agent_config={
                "name": "Assistente de Teste",
                "type": "general",
                "description": "Assistente para testes do sistema Resync"
            }
        )
        print(f"✅ Agent response: {agent_response[:100]}...")
        
        print("\n🎯 All LLM service tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing LLM service: {e}")
        return False

if __name__ == "__main__":
    print("🧪 LLM Service Test Suite")
    print("=" * 50)
    
    success = asyncio.run(test_llm_service())
    
    if success:
        print("\n✅ LLM service is ready for integration!")
    else:
        print("\n❌ LLM service test failed. Please check the configuration.")
