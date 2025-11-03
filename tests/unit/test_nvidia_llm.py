"""
Test script for NVIDIA LLM API
"""
import os
import pytest
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

def test_nvidia_llm():
    """Test NVIDIA LLM API connection and response"""
    try:
        # Get API key from environment
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            pytest.skip("NVIDIA_API_KEY not set")

        # Initialize OpenAI client with NVIDIA API
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )

        print("🚀 Testing NVIDIA LLM API...")
        print("📡 Using model: nvidia/llama-3.3-nemotron-super-49b-v1.5")
        print("=" * 50)

        # Create completion request
        completion = client.chat.completions.create(
            model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
            messages=[
                {"role": "system", "content": "Você é um assistente útil que responde em português de forma clara e concisa."},
                {"role": "user", "content": "Olá! Por favor, me diga como está o sistema Resync TWS Integration."}
            ],
            temperature=0.6,
            top_p=0.95,
            max_tokens=500,
            frequency_penalty=0,
            presence_penalty=0,
            stream=False  # Set to False for testing
        )

        # Print response
        print("✅ API Response received:")
        print(completion.choices[0].message.content)
        print("=" * 50)
        print("🎉 NVIDIA LLM API is working correctly!")
        return True

    except Exception as e:
        print(f"❌ Error testing NVIDIA LLM API: {e}")
        return False

def test_streaming():
    """Test streaming response from NVIDIA LLM API"""
    try:
        # Get API key from environment
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            pytest.skip("NVIDIA_API_KEY not set")

        # Initialize OpenAI client with NVIDIA API
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )

        print("\n🌊 Testing streaming response...")
        print("=" * 50)

        # Create streaming completion request
        completion = client.chat.completions.create(
            model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
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
        for chunk in completion:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                print(content, end="")
                full_response += content

        print("\n" + "=" * 50)
        print("🎉 Streaming response completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error testing streaming: {e}")
        return False

if __name__ == "__main__":
    print("🧪 NVIDIA LLM API Test Suite")
    print("=" * 50)

    # Test basic completion
    basic_test = test_nvidia_llm()

    # Test streaming
    streaming_test = test_streaming()

    # Summary
    print("\n📊 Test Summary:")
    print(f"Basic completion: {'✅ PASS' if basic_test else '❌ FAIL'}")
    print(f"Streaming: {'✅ PASS' if streaming_test else '❌ FAIL'}")

    if basic_test and streaming_test:
        print("\n🎯 All tests passed! NVIDIA LLM is ready for integration.")
    else:
        print("\n⚠️  Some tests failed. Please check the configuration.")




