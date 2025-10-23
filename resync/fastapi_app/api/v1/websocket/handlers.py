
from fastapi import WebSocket
from typing import Dict, Set
import json
import logging

# Store active WebSocket connections
active_connections: Dict[str, Set[WebSocket]] = {}

logger = logging.getLogger(__name__)

async def connect_websocket(websocket: WebSocket, agent_id: str) -> None:
    """
    Connect a WebSocket and add to active connections
    """
    await websocket.accept()
    
    # Add to active connections
    if agent_id not in active_connections:
        active_connections[agent_id] = set()
    active_connections[agent_id].add(websocket)
    
    logger.info(f"WebSocket connected for agent {agent_id}")

async def disconnect_websocket(websocket: WebSocket, agent_id: str) -> None:
    """
    Disconnect a WebSocket and remove from active connections
    """
    if agent_id in active_connections:
        active_connections[agent_id].discard(websocket)
        if not active_connections[agent_id]:
            del active_connections[agent_id]
    
    logger.info(f"WebSocket disconnected for agent {agent_id}")

async def send_personal_message(message: str, websocket: WebSocket) -> None:
    """
    Send a message to a specific WebSocket
    """
    await websocket.send_text(message)

async def broadcast_message(message: str, agent_id: str) -> None:
    """
    Broadcast a message to all WebSockets for an agent
    """
    if agent_id in active_connections:
        # Create a copy of the set to avoid modification during iteration
        connections = active_connections[agent_id].copy()
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to WebSocket: {e}")
                # Remove dead connections
                active_connections[agent_id].discard(connection)

async def handle_websocket_message(data: str, websocket: WebSocket, agent_id: str) -> None:
    """
    Handle incoming WebSocket message
    """
    try:
        # Parse JSON message
        message_data = json.loads(data)
        
        # Process message based on type
        message_type = message_data.get("type", "unknown")
        
        if message_type == "ping":
            await send_personal_message(json.dumps({"type": "pong"}), websocket)
        elif message_type == "chat":
            # Echo chat messages
            response = {
                "type": "chat_response",
                "message": f"Echo: {message_data.get('message', '')}",
                "timestamp": message_data.get("timestamp")
            }
            await send_personal_message(json.dumps(response), websocket)
        else:
            # Unknown message type
            response = {
                "type": "error",
                "message": f"Unknown message type: {message_type}"
            }
            await send_personal_message(json.dumps(response), websocket)
            
    except json.JSONDecodeError:
        # Handle non-JSON messages
        response = {
            "type": "error",
            "message": "Invalid JSON format"
        }
        await send_personal_message(json.dumps(response), websocket)
    except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")
        response = {
            "type": "error",
            "message": "Internal server error"
        }
        await send_personal_message(json.dumps(response), websocket)
