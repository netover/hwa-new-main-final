# Resync Usage Examples

## Table of Contents

1. [Quick Start](#quick-start)
2. [WebSocket Chat Integration](#websocket-chat-integration)
3. [REST API Usage](#rest-api-usage)
4. [File Upload and Processing](#file-upload-and-processing)
5. [TWS Integration](#tws-integration)
6. [Knowledge Graph Operations](#knowledge-graph-operations)
7. [Audit System Usage](#audit-system-usage)
8. [Error Handling](#error-handling)
9. [Advanced Examples](#advanced-examples)

## Quick Start

### 1. Basic Setup

```python
# Install dependencies
pip install -r requirements/dev.txt

# Set environment variables
export TWS_HOST=your-tws-host
export TWS_PORT=31116
export TWS_USER=your-username
export TWS_PASSWORD=your-password
export TWS_MOCK_MODE=false  # Set to true for testing

# Start the application
uvicorn resync.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Create Agent Configuration

Create `agents.json`:

```json
{
  "agents": [
    {
      "id": "tws-specialist",
      "name": "TWS Specialist",
      "role": "TWS Environment Expert",
      "goal": "Help with TWS troubleshooting and monitoring",
      "backstory": "Expert in TWS operations and job scheduling",
      "tools": ["tws_status_tool", "tws_troubleshooting_tool"],
      "model_name": "llama3:latest",
      "memory": true,
      "verbose": false
    },
    {
      "id": "file-helper",
      "name": "File Processing Assistant",
      "role": "Document Processing Expert",
      "goal": "Help with document analysis and processing",
      "backstory": "Specialized in document understanding and text extraction",
      "tools": [],
      "model_name": "llama3:latest",
      "memory": true,
      "verbose": false
    }
  ]
}
```

### 3. Test the Application

```bash
# Check application health
curl http://localhost:8000/api/health/app

# Check TWS connection
curl http://localhost:8000/api/health/tws

# Get available agents
curl http://localhost:8000/api/agents

# Get TWS status
curl http://localhost:8000/api/status
```

## WebSocket Chat Integration

### 1. Basic WebSocket Client

```python
import asyncio
import websockets
import json

async def chat_with_agent(agent_id: str, message: str):
    """Basic WebSocket chat client."""
    uri = f"ws://localhost:8000/ws/{agent_id}"
    
    async with websockets.connect(uri) as websocket:
        # Send message
        await websocket.send(message)
        
        # Receive response
        async for response in websocket:
            data = json.loads(response)
            print(f"{data['sender']}: {data['message']}")
            
            if data.get('is_final'):
                break

# Usage
asyncio.run(chat_with_agent("tws-specialist", "What's the status of the TWS system?"))
```

### 2. Advanced WebSocket Client with Error Handling

```python
import asyncio
import websockets
import json
import logging

class ResyncChatClient:
    def __init__(self, agent_id: str, base_url: str = "ws://localhost:8000"):
        self.agent_id = agent_id
        self.uri = f"{base_url}/ws/{agent_id}"
        self.websocket = None
        self.logger = logging.getLogger(__name__)
    
    async def connect(self):
        """Connect to the WebSocket."""
        try:
            self.websocket = await websockets.connect(self.uri)
            self.logger.info(f"Connected to agent: {self.agent_id}")
        except Exception as e:
            self.logger.error(f"Failed to connect: {e}")
            raise
    
    async def send_message(self, message: str):
        """Send a message to the agent."""
        if not self.websocket:
            raise ConnectionError("Not connected to WebSocket")
        
        try:
            await self.websocket.send(message)
            self.logger.info(f"Sent message: {message}")
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            raise
    
    async def receive_messages(self, callback):
        """Receive messages from the agent."""
        if not self.websocket:
            raise ConnectionError("Not connected to WebSocket")
        
        try:
            async for response in self.websocket:
                data = json.loads(response)
                await callback(data)
                
                if data.get('is_final'):
                    break
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("WebSocket connection closed")
        except Exception as e:
            self.logger.error(f"Error receiving messages: {e}")
            raise
    
    async def close(self):
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            self.logger.info("WebSocket connection closed")

# Usage
async def message_handler(data):
    """Handle incoming messages."""
    print(f"{data['sender']}: {data['message']}")

async def main():
    client = ResyncChatClient("tws-specialist")
    
    try:
        await client.connect()
        
        # Start receiving messages in background
        receive_task = asyncio.create_task(
            client.receive_messages(message_handler)
        )
        
        # Send messages
        await client.send_message("What's the current status of workstations?")
        await asyncio.sleep(2)
        
        await client.send_message("Are there any failed jobs?")
        await asyncio.sleep(2)
        
        # Wait for responses
        await receive_task
        
    finally:
        await client.close()

# Run the client
asyncio.run(main())
```

### 3. JavaScript WebSocket Client

```javascript
class ResyncChat {
    constructor(agentId, baseUrl = 'ws://localhost:8000') {
        this.agentId = agentId;
        this.ws = null;
        this.baseUrl = baseUrl;
        this.messageHandlers = [];
    }
    
    connect() {
        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(`${this.baseUrl}/ws/${this.agentId}`);
            
            this.ws.onopen = () => {
                console.log('Connected to agent:', this.agentId);
                resolve();
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };
            
            this.ws.onclose = () => {
                console.log('Disconnected from agent');
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                reject(error);
            };
        });
    }
    
    sendMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(message);
        } else {
            throw new Error('WebSocket not connected');
        }
    }
    
    handleMessage(data) {
        this.messageHandlers.forEach(handler => handler(data));
    }
    
    onMessage(handler) {
        this.messageHandlers.push(handler);
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Usage
const chat = new ResyncChat('tws-specialist');

chat.onMessage((data) => {
    console.log(`${data.sender}: ${data.message}`);
});

chat.connect().then(() => {
    chat.sendMessage("What's the status of the TWS system?");
});
```

## REST API Usage

### 1. Python HTTP Client

```python
import httpx
import asyncio
from typing import Dict, Any

class ResyncAPIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def get_agents(self) -> list:
        """Get all available agents."""
        response = await self.client.get(f"{self.base_url}/api/agents")
        return response.json()
    
    async def get_tws_status(self) -> Dict[str, Any]:
        """Get TWS system status."""
        response = await self.client.get(f"{self.base_url}/api/status")
        return response.json()
    
    async def get_health(self) -> Dict[str, str]:
        """Get application health."""
        response = await self.client.get(f"{self.base_url}/api/health/app")
        return response.json()
    
    async def get_tws_health(self) -> Dict[str, str]:
        """Get TWS connection health."""
        response = await self.client.get(f"{self.base_url}/api/health/tws")
        return response.json()
    
    async def get_metrics(self) -> str:
        """Get application metrics."""
        response = await self.client.get(f"{self.base_url}/api/metrics")
        return response.text
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

# Usage
async def main():
    client = ResyncAPIClient()
    
    try:
        # Get agents
        agents = await client.get_agents()
        print("Available agents:", agents)
        
        # Get TWS status
        status = await client.get_tws_status()
        print("TWS Status:", status)
        
        # Get health
        health = await client.get_health()
        print("App Health:", health)
        
    finally:
        await client.close()

asyncio.run(main())
```

### 2. cURL Examples

```bash
# Get all agents
curl -X GET "http://localhost:8000/api/agents" \
  -H "Content-Type: application/json"

# Get TWS status
curl -X GET "http://localhost:8000/api/status" \
  -H "Content-Type: application/json"

# Get application health
curl -X GET "http://localhost:8000/api/health/app" \
  -H "Content-Type: application/json"

# Get TWS health
curl -X GET "http://localhost:8000/api/health/tws" \
  -H "Content-Type: application/json"

# Get metrics
curl -X GET "http://localhost:8000/api/metrics" \
  -H "Content-Type: text/plain"
```

## File Upload and Processing

### 1. Python File Upload Client

```python
import httpx
import asyncio
from pathlib import Path

class ResyncFileUploader:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def upload_file(self, file_path: str) -> Dict[str, Any]:
        """Upload a file for RAG processing."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/octet-stream')}
            response = await self.client.post(
                f"{self.base_url}/api/rag/upload",
                files=files
            )
            return response.json()
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

# Usage
async def upload_documents():
    uploader = ResyncFileUploader()
    
    try:
        # Upload a PDF document
        result = await uploader.upload_file("document.pdf")
        print(f"Uploaded: {result['filename']}")
        
        # Upload a Word document
        result = await uploader.upload_file("manual.docx")
        print(f"Uploaded: {result['filename']}")
        
        # Upload an Excel file
        result = await uploader.upload_file("data.xlsx")
        print(f"Uploaded: {result['filename']}")
        
    finally:
        await uploader.close()

asyncio.run(upload_documents())
```

### 2. cURL File Upload

```bash
# Upload a PDF file
curl -X POST "http://localhost:8000/api/rag/upload" \
  -F "file=@document.pdf"

# Upload a Word document
curl -X POST "http://localhost:8000/api/rag/upload" \
  -F "file=@manual.docx"

# Upload an Excel file
curl -X POST "http://localhost:8000/api/rag/upload" \
  -F "file=@data.xlsx"
```

### 3. Batch File Upload

```python
import asyncio
import httpx
from pathlib import Path
from typing import List

async def upload_multiple_files(file_paths: List[str]) -> List[Dict[str, Any]]:
    """Upload multiple files concurrently."""
    async with httpx.AsyncClient() as client:
        tasks = []
        
        for file_path in file_paths:
            task = upload_single_file(client, file_path)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

async def upload_single_file(client: httpx.AsyncClient, file_path: str) -> Dict[str, Any]:
    """Upload a single file."""
    file_path = Path(file_path)
    
    with open(file_path, 'rb') as f:
        files = {'file': (file_path.name, f, 'application/octet-stream')}
        response = await client.post(
            "http://localhost:8000/api/rag/upload",
            files=files
        )
        return response.json()

# Usage
file_paths = ["doc1.pdf", "doc2.docx", "doc3.xlsx"]
results = await upload_multiple_files(file_paths)

for result in results:
    if isinstance(result, Exception):
        print(f"Upload failed: {result}")
    else:
        print(f"Uploaded: {result['filename']}")
```

## TWS Integration

### 1. TWS Status Monitoring

```python
import asyncio
import httpx
from typing import Dict, Any

class TWSMonitor:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def get_workstations(self) -> List[Dict[str, Any]]:
        """Get workstation status."""
        response = await self.client.get(f"{self.base_url}/api/status")
        data = response.json()
        return data.get('workstations', [])
    
    async def get_jobs(self) -> List[Dict[str, Any]]:
        """Get job status."""
        response = await self.client.get(f"{self.base_url}/api/status")
        data = response.json()
        return data.get('jobs', [])
    
    async def get_critical_jobs(self) -> List[Dict[str, Any]]:
        """Get critical path jobs."""
        response = await self.client.get(f"{self.base_url}/api/status")
        data = response.json()
        return data.get('critical_jobs', [])
    
    async def monitor_system(self, interval: int = 30):
        """Monitor TWS system continuously."""
        while True:
            try:
                workstations = await self.get_workstations()
                jobs = await self.get_jobs()
                critical_jobs = await self.get_critical_jobs()
                
                # Check for issues
                down_workstations = [w for w in workstations if w['status'] != 'LINKED']
                failed_jobs = [j for j in jobs if j['status'] == 'ABEND']
                
                if down_workstations:
                    print(f"⚠️  Down workstations: {len(down_workstations)}")
                    for ws in down_workstations:
                        print(f"   - {ws['name']}: {ws['status']}")
                
                if failed_jobs:
                    print(f"❌ Failed jobs: {len(failed_jobs)}")
                    for job in failed_jobs:
                        print(f"   - {job['name']} on {job['workstation']}")
                
                if not down_workstations and not failed_jobs:
                    print("✅ System healthy")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                print(f"❌ Monitoring error: {e}")
                await asyncio.sleep(interval)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

# Usage
async def main():
    monitor = TWSMonitor()
    
    try:
        await monitor.monitor_system(interval=60)  # Check every minute
    except KeyboardInterrupt:
        print("Monitoring stopped")
    finally:
        await monitor.close()

asyncio.run(main())
```

### 2. TWS Health Check Script

```python
import asyncio
import httpx
import sys

async def check_tws_health():
    """Check TWS system health."""
    async with httpx.AsyncClient() as client:
        try:
            # Check application health
            response = await client.get("http://localhost:8000/api/health/app")
            if response.status_code != 200:
                print("❌ Application health check failed")
                return False
            
            # Check TWS connection
            response = await client.get("http://localhost:8000/api/health/tws")
            if response.status_code != 200:
                print("❌ TWS connection health check failed")
                return False
            
            # Get system status
            response = await client.get("http://localhost:8000/api/status")
            if response.status_code != 200:
                print("❌ TWS status check failed")
                return False
            
            data = response.json()
            workstations = data.get('workstations', [])
            jobs = data.get('jobs', [])
            
            print(f"✅ TWS System Healthy")
            print(f"   - Workstations: {len(workstations)}")
            print(f"   - Jobs: {len(jobs)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False

# Usage
if __name__ == "__main__":
    success = asyncio.run(check_tws_health())
    sys.exit(0 if success else 1)
```

## Knowledge Graph Operations

### 1. Conversation Storage

```python
import asyncio
import httpx
from typing import Dict, Any

class KnowledgeGraphClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def store_conversation(self, user_query: str, agent_response: str, agent_id: str, context: Dict[str, Any] = None):
        """Store a conversation in the knowledge graph."""
        # This would typically be done through the WebSocket chat
        # but can also be done programmatically
        pass
    
    async def search_similar_issues(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar issues in the knowledge graph."""
        # This is typically done internally by the system
        # but can be exposed through additional endpoints
        pass

# Usage example for storing conversations
async def store_conversation_example():
    # This is typically handled automatically by the chat system
    # but here's how it would work programmatically
    
    # The conversation is automatically stored when using WebSocket chat
    # The system will:
    # 1. Store the user query and agent response
    # 2. Add context about the agent and system state
    # 3. Make it searchable for future similar queries
    pass
```

### 2. Knowledge Graph Search

```python
# The knowledge graph search is typically handled internally
# but here's how it works:

# When a user asks a question through WebSocket chat:
# 1. The system searches for similar past conversations
# 2. Retrieves relevant context from the knowledge graph
# 3. Enhances the agent's response with this context
# 4. Stores the new conversation for future reference

# This happens automatically in the WebSocket chat endpoint
```

## Audit System Usage

### 1. Get Flagged Memories

```python
import asyncio
import httpx

async def get_flagged_memories():
    """Get memories flagged for human review."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/audit/flags")
        return response.json()

# Usage
flagged_memories = await get_flagged_memories()
for memory in flagged_memories:
    print(f"Memory ID: {memory['id']}")
    print(f"User Query: {memory['user_query']}")
    print(f"Agent Response: {memory['agent_response']}")
    print(f"Status: {memory['status']}")
    print("---")
```

### 2. Review Flagged Memories

```python
import asyncio
import httpx

async def review_memory(memory_id: str, action: str):
    """Review a flagged memory."""
    async with httpx.AsyncClient() as client:
        data = {
            "memory_id": memory_id,
            "action": action  # "approve" or "reject"
        }
        response = await client.post("http://localhost:8000/api/audit/review", json=data)
        return response.json()

# Usage
# Approve a memory
result = await review_memory("mem_123", "approve")
print(f"Memory approved: {result}")

# Reject a memory
result = await review_memory("mem_456", "reject")
print(f"Memory rejected: {result}")
```

### 3. Get Audit Metrics

```python
import asyncio
import httpx

async def get_audit_metrics():
    """Get audit queue metrics."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/audit/metrics")
        return response.json()

# Usage
metrics = await get_audit_metrics()
print(f"Pending: {metrics.get('pending', 0)}")
print(f"Approved: {metrics.get('approved', 0)}")
print(f"Rejected: {metrics.get('rejected', 0)}")
```

## Error Handling

### 1. Comprehensive Error Handling

```python
import asyncio
import httpx
from typing import Optional, Dict, Any

class ResyncClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def safe_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Make a safe HTTP request with error handling."""
        try:
            response = await self.client.request(method, f"{self.base_url}{endpoint}", **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error {e.response.status_code}: {e.response.text}")
            return None
        except httpx.RequestError as e:
            print(f"Request error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
    
    async def get_agents_safe(self) -> Optional[List[Dict[str, Any]]]:
        """Safely get all agents."""
        return await self.safe_request("GET", "/api/agents")
    
    async def get_status_safe(self) -> Optional[Dict[str, Any]]:
        """Safely get TWS status."""
        return await self.safe_request("GET", "/api/status")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

# Usage
async def main():
    client = ResyncClient()
    
    try:
        # Safe agent retrieval
        agents = await client.get_agents_safe()
        if agents:
            print(f"Found {len(agents)} agents")
        else:
            print("Failed to retrieve agents")
        
        # Safe status retrieval
        status = await client.get_status_safe()
        if status:
            print(f"TWS Status: {status}")
        else:
            print("Failed to retrieve TWS status")
    
    finally:
        await client.close()

asyncio.run(main())
```

### 2. Retry Logic

```python
import asyncio
import httpx
from typing import Optional, Dict, Any

class ResyncClientWithRetry:
    def __init__(self, base_url: str = "http://localhost:8000", max_retries: int = 3):
        self.base_url = base_url
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def request_with_retry(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Make a request with retry logic."""
        for attempt in range(self.max_retries):
            try:
                response = await self.client.request(method, f"{self.base_url}{endpoint}", **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:  # Server error, retry
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                print(f"HTTP error {e.response.status_code}: {e.response.text}")
                return None
            except httpx.RequestError as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                print(f"Request error: {e}")
                return None
            except Exception as e:
                print(f"Unexpected error: {e}")
                return None
        
        return None
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

# Usage
async def main():
    client = ResyncClientWithRetry()
    
    try:
        # Request with retry
        agents = await client.request_with_retry("GET", "/api/agents")
        if agents:
            print(f"Found {len(agents)} agents")
        else:
            print("Failed to retrieve agents after retries")
    
    finally:
        await client.close()

asyncio.run(main())
```

## Advanced Examples

### 1. Complete Integration Example

```python
import asyncio
import websockets
import httpx
import json
from typing import Dict, Any, List

class ResyncIntegration:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.http_client = httpx.AsyncClient()
    
    async def get_system_overview(self) -> Dict[str, Any]:
        """Get a complete system overview."""
        try:
            # Get agents
            agents_response = await self.http_client.get(f"{self.base_url}/api/agents")
            agents = agents_response.json()
            
            # Get TWS status
            status_response = await self.http_client.get(f"{self.base_url}/api/status")
            status = status_response.json()
            
            # Get health
            health_response = await self.http_client.get(f"{self.base_url}/api/health/app")
            health = health_response.json()
            
            return {
                "agents": agents,
                "tws_status": status,
                "health": health
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def chat_with_agent(self, agent_id: str, message: str) -> str:
        """Chat with an agent and return the response."""
        uri = f"ws://localhost:8000/ws/{agent_id}"
        response_parts = []
        
        try:
            async with websockets.connect(uri) as websocket:
                await websocket.send(message)
                
                async for response in websocket:
                    data = json.loads(response)
                    if data['type'] == 'stream':
                        response_parts.append(data['message'])
                    elif data['type'] == 'message' and data.get('is_final'):
                        response_parts.append(data['message'])
                        break
                
                return ''.join(response_parts)
        except Exception as e:
            return f"Error: {e}"
    
    async def upload_and_process_file(self, file_path: str) -> Dict[str, Any]:
        """Upload a file and return the result."""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = await self.http_client.post(
                    f"{self.base_url}/api/rag/upload",
                    files=files
                )
                return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def close(self):
        """Close all connections."""
        await self.http_client.aclose()

# Usage
async def main():
    integration = ResyncIntegration()
    
    try:
        # Get system overview
        overview = await integration.get_system_overview()
        print("System Overview:", overview)
        
        # Chat with an agent
        response = await integration.chat_with_agent("tws-specialist", "What's the status?")
        print("Agent Response:", response)
        
        # Upload a file
        result = await integration.upload_and_process_file("document.pdf")
        print("Upload Result:", result)
    
    finally:
        await integration.close()

asyncio.run(main())
```

### 2. Monitoring Dashboard

```python
import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, Any, List

class ResyncMonitor:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
        self.metrics = []
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect system metrics."""
        try:
            # Get system status
            status_response = await self.client.get(f"{self.base_url}/api/status")
            status = status_response.json()
            
            # Get health
            health_response = await self.client.get(f"{self.base_url}/api/health/app")
            health = health_response.json()
            
            # Get TWS health
            tws_health_response = await self.client.get(f"{self.base_url}/api/health/tws")
            tws_health = tws_health_response.json()
            
            # Get metrics
            metrics_response = await self.client.get(f"{self.base_url}/api/metrics")
            metrics_text = metrics_response.text
            
            return {
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "health": health,
                "tws_health": tws_health,
                "metrics": metrics_text
            }
        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    async def monitor_continuously(self, interval: int = 60):
        """Monitor the system continuously."""
        while True:
            metrics = await self.collect_metrics()
            self.metrics.append(metrics)
            
            # Keep only last 100 metrics
            if len(self.metrics) > 100:
                self.metrics = self.metrics[-100:]
            
            # Print current status
            if "error" in metrics:
                print(f"❌ {metrics['timestamp']}: {metrics['error']}")
            else:
                workstations = len(metrics['status']['workstations'])
                jobs = len(metrics['status']['jobs'])
                print(f"✅ {metrics['timestamp']}: {workstations} workstations, {jobs} jobs")
            
            await asyncio.sleep(interval)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

# Usage
async def main():
    monitor = ResyncMonitor()
    
    try:
        await monitor.monitor_continuously(interval=30)  # Check every 30 seconds
    except KeyboardInterrupt:
        print("Monitoring stopped")
    finally:
        await monitor.close()

asyncio.run(main())
```

This comprehensive usage examples guide provides practical examples for integrating with the Resync system, handling errors, and building monitoring solutions.