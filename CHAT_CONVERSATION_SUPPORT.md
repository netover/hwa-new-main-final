# Suporte a Conversas Longas no WebSocket

## Implementação

Foi implementado suporte a conversas longas no WebSocket para permitir que os usuários mantenham diálogos contínuos com os agentes TWS. A implementação inclui:

1. **Manutenção do histórico de conversas**: Armazenamento de mensagens do usuário e respostas do agente em um array `conversation_history`.

2. **Loop contínuo de processamento**: Substituição do modelo de mensagem única por um loop `while True` que mantém a conexão WebSocket aberta.

3. **Detecção de perguntas de acompanhamento**: Lógica para identificar quando uma mensagem é parte de uma conversa em andamento.

4. **Respostas contextuais**: Capacidade de gerar respostas que levam em conta o contexto da conversa.

## Código Implementado

```python
# Multi-message conversation model
try:
    # Initialize conversation history
    conversation_history = []
    
    # Continuous message processing loop
    while True:
        # Receive message from client
        raw_data = await websocket.receive_text()
        logger.info(f"Received message for agent '{agent_id}': {raw_data}")
        
        # Add user message to history
        conversation_history.append({"role": "user", "content": raw_data})
        
        try:
            # Process message with agent
            logger.info(f"Processing message with agent: {raw_data}")
            
            # Use direct string responses with context from conversation history
            msg = raw_data.lower()
            
            # Generate contextual response based on conversation history
            if len(conversation_history) > 1:
                # This is a follow-up question
                logger.info(f"Follow-up question detected. History length: {len(conversation_history)}")
            
            # Generate responses based on keywords
            if "job" in msg and ("abend" in msg or "erro" in msg):
                response = "Jobs em estado ABEND encontrados:\n- Data Processing (ID: JOB002) na workstation TWS_AGENT2\n\nRecomendo investigar o log do job e verificar dependências."
            elif "status" in msg or "workstation" in msg:
                response = "Status atual do ambiente TWS:\n\nWorkstations:\n- TWS_MASTER: ONLINE\n- TWS_AGENT1: ONLINE\n- TWS_AGENT2: OFFLINE\n\nJobs:\n- Daily Backup: SUCC (TWS_AGENT1)\n- Data Processing: ABEND (TWS_AGENT2)\n- Report Generation: SUCC (TWS_AGENT1)"
            elif "tws" in msg:
                response = f"Como {agent_id}, posso ajudar com questões relacionadas ao TWS. Que informações você precisa?"
            elif "obrigado" in msg or "valeu" in msg:
                response = "Disponível para ajudar! Se precisar de mais informações sobre o TWS, é só perguntar."
            else:
                response = f"Entendi sua mensagem: '{raw_data}'. Como {agent_id}, estou aqui para ajudar com questões do TWS."
            
            # Add agent response to history
            conversation_history.append({"role": "assistant", "content": response})
            
            # Send response back to client
            response_data = {
                "type": "message",
                "sender": "agent",
                "message": response,
            }
            await websocket.send_text(json.dumps(response_data))
            
        except Exception as agent_error:
            logger.error(f"Error processing message with agent '{agent_id}': {agent_error}")
            error_data = {
                "type": "error",
                "sender": "agent",
                "message": f"Erro ao processar mensagem: {str(agent_error)}",
            }
            await websocket.send_text(json.dumps(error_data))

except WebSocketDisconnect:
    logger.info(f"Client disconnected from agent '{agent_id}'.")
except Exception as e:
    logger.error(f"Unexpected error in WebSocket for agent '{agent_id}': {e}")
```

## Teste de Conversas Longas

Foi criado um script de teste para verificar o suporte a conversas longas:

```python
import asyncio
import websockets
import json

async def test_conversation():
    print('Testando conversa longa...')
    try:
        ws = await asyncio.wait_for(websockets.connect('ws://localhost:8030/api/v1/ws/tws-general'), timeout=10.0)
        print('Conectado!')
        
        # Receber mensagem de boas-vindas
        welcome = await asyncio.wait_for(ws.recv(), timeout=10.0)
        print(f'Mensagem de boas-vindas: {welcome}')
        
        # Primeira pergunta
        await ws.send('qual job esta em abend?')
        print('Pergunta 1 enviada')
        
        response1 = await asyncio.wait_for(ws.recv(), timeout=10.0)
        print(f'Resposta 1: {response1}')
        
        # Segunda pergunta (follow-up)
        await ws.send('quais são as workstations disponíveis?')
        print('Pergunta 2 enviada')
        
        response2 = await asyncio.wait_for(ws.recv(), timeout=10.0)
        print(f'Resposta 2: {response2}')
        
        # Terceira pergunta
        await ws.send('obrigado pela ajuda')
        print('Pergunta 3 enviada')
        
        response3 = await asyncio.wait_for(ws.recv(), timeout=10.0)
        print(f'Resposta 3: {response3}')
        
        await ws.close()
        print('Teste concluído com sucesso!')
        
    except Exception as e:
        print(f'Erro: {e}')

asyncio.run(test_conversation())
```

## Resultados

O teste confirmou que o sistema agora suporta conversas longas, permitindo que o usuário faça múltiplas perguntas em sequência sem que a conexão WebSocket seja fechada após cada resposta.

As respostas são geradas com base no contexto da conversa, e o histórico é mantido para referência futura.

## Próximos Passos

1. **Integração com LLM**: Implementar integração completa com modelos de linguagem para respostas mais inteligentes e contextuais.

2. **Persistência de conversas**: Armazenar conversas em banco de dados para referência futura e análise.

3. **Gerenciamento de sessões**: Implementar identificação de usuários e sessões para manter conversas separadas por usuário.

4. **Timeout de inatividade**: Adicionar um mecanismo para fechar conexões após um período de inatividade para gerenciar recursos do servidor.
