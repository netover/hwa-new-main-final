#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug detalhado da configuração e conectividade LLM API
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def debug_llm_configuration():
    """Debug completo da configuração LLM"""
    print("🔍 DEBUG DETALHADO DA CONFIGURAÇÃO LLM")
    print("=" * 60)
    
    try:
        # Import settings
        from resync.settings import settings
        
        print("📋 CONFIGURAÇÃO ATUAL:")
        print(f"   LLM Endpoint: {settings.llm_endpoint}")
        print(f"   LLM API Key: {settings.llm_api_key[:20]}...{settings.llm_api_key[-10:]}")
        print(f"   LLM Timeout: {settings.llm_timeout}s")
        print(f"   Environment: {settings.environment}")
        
        # Verificar configurações do .env
        print("\n📁 ARQUIVO .ENV:")
        env_file = Path('.env')
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines:
                    if any(key in line.upper() for key in ['LLM_', 'ENDPOINT', 'API_KEY', 'MODEL']):
                        print(f"   {line.strip()}")
        else:
            print("   ❌ Arquivo .env não encontrado")
        
        # Testar LLM Service
        print("\n🧪 TESTE DO LLM SERVICE:")
        from resync.services.llm_service import get_llm_service
        
        llm_service = get_llm_service()
        print(f"   ✅ LLM Service inicializado")
        print(f"   📱 Modelo: {llm_service.model}")
        print(f"   🌐 Base URL: {llm_service.client.base_url}")
        print(f"   🔑 API Key: {llm_service.client.api_key[:20]}...{llm_service.client.api_key[-10:]}")
        
        # Teste de conectividade básica
        print("\n🌐 TESTE DE CONECTIVIDADE:")
        try:
            import aiohttp
            
            # Testar endpoint base
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Bearer {settings.llm_api_key}',
                    'Content-Type': 'application/json'
                }
                
                print(f"   📡 Testando endpoint: {settings.llm_endpoint}")
                
                # Testar se endpoint responde
                async with session.get(f"{settings.llm_endpoint}/models", headers=headers) as response:
                    print(f"   📊 Status Code: {response.status}")
                    if response.status == 200:
                        models = await response.json()
                        print(f"   ✅ Endpoint respondeu - {len(models.get('data', []))} modelos disponíveis")
                        for model in models.get('data', [])[:3]:
                            print(f"      - {model.get('id', 'Unknown')}")
                    else:
                        error_text = await response.text()
                        print(f"   ❌ Erro: {error_text}")
                        
        except Exception as e:
            print(f"   ❌ Erro de conectividade: {e}")
        
        # Teste de health check do LLM service
        print("\n🏥 HEALTH CHECK DO LLM:")
        try:
            health_status = await llm_service.health_check()
            print(f"   Status: {health_status['status']}")
            print(f"   Model: {health_status['model']}")
            print(f"   Endpoint: {health_status['endpoint']}")
            
            if 'error' in health_status:
                print(f"   ❌ Erro: {health_status['error']}")
            elif 'test_response' in health_status:
                print(f"   ✅ Test Response: {health_status['test_response']}")
                
        except Exception as e:
            print(f"   ❌ Erro no health check: {e}")
        
        # Teste de geração de resposta
        print("\n💬 TESTE DE GERAÇÃO DE RESPOSTA:")
        try:
            messages = [
                {"role": "user", "content": "Responda apenas com 'OK' para teste."}
            ]
            
            response = await llm_service.generate_response(messages, max_tokens=10)
            print(f"   ✅ Resposta gerada: {response}")
            
        except Exception as e:
            print(f"   ❌ Erro na geração: {e}")
            print(f"   📝 Tipo do erro: {type(e).__name__}")
            if hasattr(e, 'details'):
                print(f"   📋 Detalhes: {e.details}")
        
        # Análise final
        print("\n📊 ANÁLISE FINAL:")
        if settings.llm_endpoint.startswith("https://integrate.api.nvidia.com"):
            print("   🔍 Usando NVIDIA API")
            print("   ⚠️  Verifique se a API key é válida para NVIDIA")
        elif settings.llm_endpoint.startswith("https://openrouter.ai"):
            print("   🔍 Usando OpenRouter API")
            print("   ⚠️  Verifique se a API key é válida para OpenRouter")
        else:
            print(f"   🔍 Usando endpoint customizado: {settings.llm_endpoint}")
            
        print("\n💡 RECOMENDAÇÕES:")
        print("   1. Verifique se a API key está correta e ativa")
        print("   2. Confirme se o endpoint está correto para o provedor")
        print("   3. Verifique limites de uso da API")
        print("   4. Teste com curl ou Postman para isolar o problema")
        
    except Exception as e:
        print(f"❌ Erro geral no debug: {e}")
        import traceback
        traceback.print_exc()

async def test_api_direct():
    """Teste direto da API com diferentes configurações"""
    print("\n🔧 TESTE DIRETO DA API (MÚLTIPLAS CONFIGS)")
    print("=" * 60)
    
    # Configurações para testar
    configs = [
        {
            "name": "NVIDIA API (config .env)",
            "endpoint": "https://integrate.api.nvidia.com/v1",
            "api_key": "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"
        },
        {
            "name": "OpenRouter (settings.py)",
            "endpoint": "https://openrouter.ai/api/v1",
            "api_key": "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"
        }
    ]
    
    try:
        from openai import AsyncOpenAI
        
        for config in configs:
            print(f"\n📡 Testando: {config['name']}")
            print(f"   Endpoint: {config['endpoint']}")
            print(f"   API Key: {config['api_key'][:20]}...{config['api_key'][-10:]}")
            
            try:
                client = AsyncOpenAI(
                    api_key=config['api_key'],
                    base_url=config['endpoint']
                )
                
                # Teste simples
                response = await client.chat.completions.create(
                    model="gpt-3.5-turbo" if "openrouter" in config['endpoint'] else "nvidia/llama-3.3-nemotron-super-49b-v1.5",
                    messages=[{"role": "user", "content": "Responda apenas com 'OK'."}],
                    max_tokens=10
                )
                
                result = response.choices[0].message.content
                print(f"   ✅ Sucesso: {result}")
                
            except Exception as e:
                print(f"   ❌ Falha: {e}")
                print(f"   📝 Tipo: {type(e).__name__}")
                
    except ImportError:
        print("   ❌ Biblioteca openai não instalada")

if __name__ == "__main__":
    asyncio.run(debug_llm_configuration())
    asyncio.run(test_api_direct())
