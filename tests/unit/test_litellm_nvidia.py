"""
Test script for NVIDIA LLM API using LiteLLM
"""
import asyncio
import os
import pytest

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_litellm_nvidia():
    """Test NVIDIA LLM API using LiteLLM"""
    try:
        # Get API key from environment
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            pytest.skip("NVIDIA_API_KEY not set")

        # Import litellm
        from litellm import acompletion

        # Set NVIDIA API key from environment
        os.environ["NVIDIA_API_KEY"] = api_key

        print("🚀 Testing NVIDIA LLM API with LiteLLM...")
        print("📡 Using model: nvidia/llama-3.3-nemotron-super-49b-v1.5")
        print("=" * 50)

        # Create completion request
        response = await acompletion(
            model="nvidia/nemotron-super-49b-v1",  # Using the model prefix for NVIDIA provider
            messages=[
                {"role": "system", "content": "Você é um assistente útil que responde em português de forma clara e concisa."},
                {"role": "user", "content": "Olá! Por favor, me diga como está o sistema Resync TWS Integration."}
            ],
            temperature=0.6,
            top_p=0.95,
            max_tokens=500,
            frequency_penalty=0,
            presence_penalty=0
        )

        # Print response
        print("✅ API Response received:")
        print(response.choices[0].message.content)
        print("=" * 50)
        print("🎉 NVIDIA LLM API with LiteLLM is working correctly!")
        return True

    except Exception as e:
        print(f"❌ Error testing NVIDIA LLM API with LiteLLM: {e}")
        return False

async def test_litellm_streaming():
    """Test streaming response using LiteLLM"""
    try:
        # Get API key from environment
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            pytest.skip("NVIDIA_API_KEY not set")

        # Import litellm streaming
        from litellm import acompletion

        # Set NVIDIA API key from environment
        os.environ["NVIDIA_API_KEY"] = api_key

        print("\n🌊 Testing streaming response with LiteLLM...")
        print("=" * 50)

        # Create streaming completion request
        response = await acompletion(
            model="nvidia/nemotron-super-49b-v1",
            messages=[
                {"role": "system", "content": "Você é um assistente útil que responde em português."},
                {"role": "user", "content": "Liste 3 benefícios principais do sistema Resync."}
            ],
            temperature=0.6,
            top_p=0.95,
            max_tokens=300,
            frequency_penalty=0,
            presence_penalty=0,
            stream=True
        )

        # Print streaming response
        print("✅ Streaming response:")
        full_response = ""
        async for chunk in response:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                print(content, end="")
                full_response += content

        print("\n" + "=" * 50)
        print("🎉 Streaming response with LiteLLM completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error testing streaming with LiteLLM: {e}")
        return False

async def main():
    """Main test function"""
    print("🧪 NVIDIA LLM API Test Suite (LiteLLM)")
    print("=" * 50)

    # Test basic completion
    basic_test = await test_litellm_nvidia()

    # Test streaming
    streaming_test = await test_litellm_streaming()

    # Summary
    print("\n📊 Test Summary:")
    print(f"Basic completion: {'✅ PASS' if basic_test else '❌ FAIL'}")
    print(f"Streaming: {'✅ PASS' if streaming_test else '❌ FAIL'}")

    if basic_test and streaming_test:
        print("\n🎯 All tests passed! NVIDIA LLM with LiteLLM is ready for integration.")
    else:
        print("\n⚠️  Some tests failed. Please check the configuration.")

if __name__ == "__main__":
    asyncio.run(main())




