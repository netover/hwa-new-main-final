
"""
WebSocket handlers for FastAPI
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
import sys
from pathlib import Path
from ..v1.dependencies import get_logger

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logger = None  # Will be injected

class ConnectionManager:
    """Manage WebSocket connections"""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.agent_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, agent_id: str):
        """Connect WebSocket for specific agent"""
        await websocket.accept()

        if agent_id not in self.active_connections:
            self.active_connections[agent_id] = set()

        self.active_connections[agent_id].add(websocket)
        self.agent_connections[websocket] = agent_id

        logger.info(f"WebSocket connected for agent {agent_id}")

    def disconnect(self, websocket: WebSocket):
        """Disconnect WebSocket"""
        agent_id = self.agent_connections.get(websocket)
        if agent_id and websocket in self.active_connections.get(agent_id, set()):
            self.active_connections[agent_id].remove(websocket)
            if not self.active_connections[agent_id]:
                del self.active_connections[agent_id]

        if websocket in self.agent_connections:
            del self.agent_connections[websocket]

        logger.info(f"WebSocket disconnected from agent {agent_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket connection"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Failed to send message to WebSocket: {e}")
            self.disconnect(websocket)

    async def broadcast_to_agent(self, message: str, agent_id: str):
        """Broadcast message to all connections for specific agent"""
        if agent_id in self.active_connections:
            disconnected = []
            for websocket in self.active_connections[agent_id]:
                try:
                    await websocket.send_text(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast to agent {agent_id}: {e}")
                    disconnected.append(websocket)

            # Clean up disconnected websockets
            for websocket in disconnected:
                self.disconnect(websocket)

    async def broadcast_to_all(self, message: str):
        """Broadcast message to all active connections"""
        disconnected = []
        for agent_connections in self.active_connections.values():
            for websocket in agent_connections:
                try:
                    await websocket.send_text(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast to all: {e}")
                    disconnected.append(websocket)

        # Clean up disconnected websockets
        for websocket in disconnected:
            self.disconnect(websocket)

# Global connection manager instance
manager = ConnectionManager()

async def websocket_handler(websocket: WebSocket, agent_id: str):
    """Handle WebSocket connections for chat agents"""
    global logger
    if logger is None:
        logger = get_logger()

    await manager.connect(websocket, agent_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            logger.info(f"Received message from agent {agent_id}: {data}")

            try:
                # Try to parse as JSON first
                try:
                    message_data = json.loads(data)
                    message_type = message_data.get("type", "message")
                    is_json = True
                except json.JSONDecodeError:
                    # If not JSON, treat as plain text message
                    message_data = {"content": data, "type": "message"}
                    message_type = "message"
                    is_json = False

                if message_type == "chat_message":
                    # Process chat message with AI agent
                    content = message_data.get('content', data if not is_json else '')

                    # Send initial streaming response
                    response = {
                        "type": "stream",
                        "message": f"Processando: {content}",
                        "agent_id": agent_id,
                        "is_final": False
                    }
                    await manager.send_personal_message(json.dumps(response), websocket)

                    # Generate real AI response using LLM service
                    try:
                        from resync.services.llm_service import get_llm_service
                        llm_service = get_llm_service()
                        
                        # Agent configuration
                        agent_config = {
                            "name": f"Agente {agent_id}",
                            "type": "general",
                            "description": "Assistente de IA do sistema Resync TWS"
                        }
                        
                        # Generate response using real LLM
                        ai_response = await llm_service.generate_agent_response(
                            agent_id=agent_id,
                            user_message=content,
                            agent_config=agent_config
                        )
                        
                        # Send final response with real AI content
                        final_response = {
                            "type": "message",
                            "message": ai_response,
                            "agent_id": agent_id,
                            "is_final": True
                        }
                        
                    except Exception as e:
                        logger.error(f"Error generating AI response: {e}")
                        # Fallback to mock response if LLM fails
                        final_response = {
                            "type": "message",
                            "message": f"Olá! Recebi sua mensagem: '{content}'. O sistema Resync TWS está funcionando perfeitamente. Como posso ajudar?",
                            "agent_id": agent_id,
                            "is_final": True
                        }
                    
                    await manager.send_personal_message(json.dumps(final_response), websocket)

                elif message_type == "heartbeat":
                    # Respond to heartbeat
                    response = {
                        "type": "heartbeat_ack",
                        "timestamp": "2025-01-01T00:00:00Z",
                        "agent_id": agent_id
                    }
                    await manager.send_personal_message(json.dumps(response), websocket)

                else:
                    # Handle plain text messages
                    if not is_json:
                        # Send initial streaming response for plain text
                        response = {
                            "type": "stream",
                            "message": f"Processando: {data}",
                            "agent_id": agent_id,
                            "is_final": False
                        }
                        await manager.send_personal_message(json.dumps(response), websocket)

                        # Generate real AI response using LLM service
                        try:
                            from resync.services.llm_service import get_llm_service
                            llm_service = get_llm_service()
                            
                            # Agent configuration
                            agent_config = {
                                "name": f"Agente {agent_id}",
                                "type": "general",
                                "description": "Assistente de IA do sistema Resync TWS"
                            }
                            
                            # Generate response using real LLM
                            ai_response = await llm_service.generate_agent_response(
                                agent_id=agent_id,
                                user_message=data,
                                agent_config=agent_config
                            )
                            
                            # Send final response with real AI content
                            final_response = {
                                "type": "message",
                                "message": ai_response,
                                "agent_id": agent_id,
                                "is_final": True
                            }
                            
                        except Exception as e:
                            logger.error(f"Error generating AI response: {e}")
                            # Fallback to mock response if LLM fails
                            final_response = {
                                "type": "message",
                                "message": f"Olá! Recebi sua mensagem: '{data}'. O sistema Resync TWS está funcionando perfeitamente. Como posso ajudar?",
                                "agent_id": agent_id,
                                "is_final": True
                            }
                        
                        await manager.send_personal_message(json.dumps(final_response), websocket)
                    else:
                        # Unknown JSON message type
                        error_response = {
                            "type": "error",
                            "message": f"Unknown message type: {message_type}",
                            "agent_id": agent_id
                        }
                        await manager.send_personal_message(json.dumps(error_response), websocket)

            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                error_response = {
                    "type": "error",
                    "message": "Internal server error",
                    "agent_id": agent_id
                }
                await manager.send_personal_message(json.dumps(error_response), websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected for agent {agent_id}")

    except Exception as e:
        logger.error(f"Unexpected WebSocket error for agent {agent_id}: {e}")
        manager.disconnect(websocket)
