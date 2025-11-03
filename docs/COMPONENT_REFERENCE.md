# Resync Component Reference

## Table of Contents

1. [Core Interfaces](#core-interfaces)
2. [Service Implementations](#service-implementations)
3. [Data Models](#data-models)
4. [Exception Handling](#exception-handling)
5. [Configuration](#configuration)

## Core Interfaces

### IAgentManager

Interface for the AgentManager component.

```python
@runtime_checkable
class IAgentManager(Protocol):
    agents: Dict[str, Any]
    agent_configs: List[AgentConfig]
    tools: Dict[str, Any]
    tws_client: Any
    _tws_init_lock: asyncio.Lock

    async def load_agents_from_config(self, config_path: Path) -> None:
        """Load agent configurations from a file."""

    async def _get_tws_client(self) -> Any:
        """Get the TWS client instance."""

    def get_agent(self, agent_id: str) -> Optional[Any]:
        """Get an agent by ID."""

    def get_all_agents(self) -> List[AgentConfig]:
        """Get all agent configurations."""

    def get_agent_with_tool(self, agent_id: str, tool_name: str) -> Optional[Any]:
        """Get an agent that has a specific tool."""
```

### IConnectionManager

Interface for the ConnectionManager component.

```python
@runtime_checkable
class IConnectionManager(Protocol):
    active_connections: List[WebSocket]

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""

    async def broadcast(self, message: str) -> None:
        """Send a message to all connected clients."""

    async def broadcast_json(self, data: Dict[str, Any]) -> None:
        """Send a JSON payload to all connected clients."""
```

### IKnowledgeGraph

Interface for the KnowledgeGraph component.

```python
@runtime_checkable
class IKnowledgeGraph(Protocol):
    data_dir: Path
    client: Any

    async def add_conversation(
        self,
        user_query: str,
        agent_response: str,
        agent_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Store a conversation in the knowledge graph."""

    async def search_similar_issues(
        self, query: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar issues in the knowledge graph."""

    async def get_relevant_context(self, user_query: str) -> str:
        """Get relevant context for a user query."""

    async def add_solution_feedback(
        self, memory_id: str, feedback: str, rating: int
    ) -> None:
        """Add user feedback to a memory."""

    async def is_memory_flagged(self, memory_id: str) -> bool:
        """Check if a memory is flagged."""

    async def is_memory_approved(self, memory_id: str) -> bool:
        """Check if a memory is approved."""

    async def delete_memory(self, memory_id: str) -> None:
        """Delete a memory."""

    async def add_observations(self, memory_id: str, observations: List[str]) -> None:
        """Add observations to a memory."""
```

### IAuditQueue

Interface for the AuditQueue component.

```python
@runtime_checkable
class IAuditQueue(Protocol):
    redis_url: str
    sync_client: Any
    async_client: Any
    distributed_lock: Any
    audit_queue_key: str
    audit_status_key: str
    audit_data_key: str

    async def add_audit_record(self, memory: Dict[str, Any]) -> bool:
        """Add a memory to the audit queue."""

    async def get_pending_audits(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get pending audits from the queue."""

    async def update_audit_status(self, memory_id: str, status: str) -> bool:
        """Update the status of an audit record."""

    async def is_memory_approved(self, memory_id: str) -> bool:
        """Check if a memory is approved."""

    async def delete_audit_record(self, memory_id: str) -> bool:
        """Remove an audit record."""

    async def get_queue_length(self) -> int:
        """Get the length of the audit queue."""

    async def get_all_audits(self) -> List[Dict[str, Any]]:
        """Get all audit records."""

    async def get_audits_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get audit records by status."""

    async def get_audit_metrics(self) -> Dict[str, int]:
        """Get metrics for the audit queue."""

    async def health_check(self) -> bool:
        """Check if Redis is accessible."""

    def get_all_audits_sync(self) -> List[Dict[str, Any]]:
        """Synchronous wrapper for get_all_audits."""

    def update_audit_status_sync(self, memory_id: str, status: str) -> bool:
        """Synchronous wrapper for update_audit_status."""
```

### IFileIngestor

Interface for the File Ingestor component.

```python
@runtime_checkable
class IFileIngestor(Protocol):
    rag_directory: Path

    async def ingest_file(self, file_path: Path) -> bool:
        """Ingests a file into the knowledge graph."""

    async def save_uploaded_file(self, file_name: str, file_content) -> Path:
        """Saves an uploaded file to the RAG directory."""
```

### ITWSClient

Interface for the TWS Client component.

```python
@runtime_checkable
class ITWSClient(Protocol):
    base_url: str
    auth: tuple
    engine_name: str
    engine_owner: str
    client: Any
    cache: Any

    async def check_connection(self) -> bool:
        """Verifies the connection to the TWS server is active."""

    async def get_workstations_status(self) -> List[Any]:
        """Retrieves the status of all workstations."""

    async def get_jobs_status(self) -> List[Any]:
        """Retrieves the status of all jobs."""

    async def get_critical_path_status(self) -> List[Any]:
        """Retrieves the status of jobs in the critical path."""

    async def get_system_status(self) -> Any:
        """Retrieves a comprehensive system status."""

    async def close(self) -> None:
        """Closes the underlying client and its connections."""
```

## Service Implementations

### AgentManager

The main service for managing AI agents.

#### Constructor
```python
def __init__(self, settings_module: Any = settings) -> None:
    """
    Initializes the AgentManager with dependencies.
    
    Args:
        settings_module: The settings module to use (default: global settings).
    """
```

#### Key Methods

##### `_discover_tools() -> Dict[str, Any]`
- **Description**: Discovers and registers available tools for the agents
- **Returns**: Dictionary of tool names to tool instances
- **Implementation**: Manually registers known tools (extensible for new tools)

##### `async _get_tws_client() -> OptimizedTWSClient`
- **Description**: Lazily initializes and returns the TWS client
- **Features**: 
  - Async-safe initialization with lock
  - Single client instance reuse
  - Automatic tool injection
- **Returns**: OptimizedTWSClient instance

##### `async load_agents_from_config(config_path: Path = None) -> None`
- **Description**: Loads agent configurations from a JSON file
- **Parameters**: `config_path` - Optional path to configuration file
- **Features**:
  - Idempotent operation
  - Comprehensive error handling
  - JSON validation
- **Raises**: Various configuration-related exceptions

##### `async _create_agents(agent_configs: List[AgentConfig]) -> Dict[str, Any]`
- **Description**: Creates agent instances based on configurations
- **Parameters**: `agent_configs` - List of agent configurations
- **Returns**: Dictionary of agent ID to agent instance
- **Features**:
  - Tool injection
  - Error handling for missing tools
  - Agent personality construction

### AsyncKnowledgeGraph

Service for managing persistent knowledge using Mem0 AI.

#### Constructor
```python
def __init__(self, data_dir: Path = Path(".mem0"), settings_module: Any = settings):
    """
    Initialize the AsyncKnowledgeGraph with Mem0 configuration.
    
    Args:
        data_dir: Directory to store persistent memory data.
        settings_module: The settings module to use (default: global settings).
    """
```

#### Key Methods

##### `async add_conversation(...) -> str`
- **Description**: Stores a conversation between a user and an agent
- **Parameters**:
  - `user_query`: The user's question or command
  - `agent_response`: The agent's response
  - `agent_id`: The ID of the agent that responded
  - `context`: Additional context to enrich the memory
- **Returns**: The unique ID of the stored memory
- **Features**: Structured memory record creation

##### `async search_similar_issues(query: str, limit: int = 5) -> List[Dict[str, Any]]`
- **Description**: Searches for similar past issues and solutions
- **Parameters**:
  - `query`: The current problem or question to match against
  - `limit`: Maximum number of similar memories to return
- **Returns**: List of relevant past memories with their metadata

##### `async get_relevant_context(user_query: str) -> str`
- **Description**: Retrieves relevant context for RAG enhancement
- **Parameters**: `user_query` - The current user query
- **Returns**: Formatted string of relevant past solutions and context
- **Features**: Structured context formatting for LLM consumption

##### `async atomic_check_and_flag(memory_id: str, reason: str, confidence: float) -> bool`
- **Description**: Atomically checks if memory is already processed, and if not, flags it
- **Parameters**:
  - `memory_id`: The ID of the memory to flag
  - `reason`: Reason for flagging
  - `confidence`: Confidence score (0.0-1.0)
- **Returns**: True if successfully flagged, False if already processed
- **Features**: Race condition prevention

### FileIngestor

Service for ingesting files into the knowledge graph.

#### Constructor
```python
def __init__(self, knowledge_graph: IKnowledgeGraph):
    """
    Initialize the FileIngestor with dependencies.
    
    Args:
        knowledge_graph: The knowledge graph service to store extracted content
    """
```

#### Supported File Types
- **PDF**: Using `pypdf` library
- **DOCX**: Using `python-docx` library  
- **XLSX**: Using `openpyxl` library

#### Key Methods

##### `async save_uploaded_file(file_name: str, file_content) -> Path`
- **Description**: Saves an uploaded file to the RAG directory
- **Parameters**:
  - `file_name`: The original filename
  - `file_content`: A file-like object containing the content
- **Returns**: Path to the saved file
- **Security**: Filename sanitization to prevent path traversal
- **Raises**: `FileProcessingError` if the file cannot be saved

##### `async ingest_file(file_path: Path) -> bool`
- **Description**: Ingests a single file into the knowledge graph
- **Parameters**: `file_path` - Path to the file to ingest
- **Returns**: True if ingestion was successful, False otherwise
- **Features**:
  - Text chunking with overlap
  - Metadata attachment
  - Error handling for individual chunks

#### Text Processing Functions

##### `chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> Iterator[str]`
- **Description**: Splits a long text into smaller chunks with overlap
- **Parameters**:
  - `text`: The text to chunk
  - `chunk_size`: Size of each chunk
  - `chunk_overlap`: Overlap between chunks
- **Returns**: Iterator of text chunks

##### `read_pdf(file_path: Path) -> str`
- **Description**: Extracts text from a PDF file
- **Parameters**: `file_path` - Path to the PDF file
- **Returns**: Extracted text content
- **Error Handling**: Comprehensive error handling for various PDF issues

##### `read_docx(file_path: Path) -> str`
- **Description**: Extracts text from a DOCX file
- **Parameters**: `file_path` - Path to the DOCX file
- **Returns**: Extracted text content
- **Error Handling**: Comprehensive error handling for various DOCX issues

##### `read_excel(file_path: Path) -> str`
- **Description**: Extracts text from an XLSX file
- **Parameters**: `file_path` - Path to the XLSX file
- **Returns**: Extracted text content from all sheets
- **Features**: Iterates through all sheets and cells
- **Error Handling**: Comprehensive error handling for various Excel issues

### OptimizedTWSClient

Optimized client for interacting with TWS APIs.

#### Constructor
```python
def __init__(
    self,
    hostname: str,
    port: int,
    username: str,
    password: str,
    engine_name: str = "tws-engine",
    engine_owner: str = "tws-owner",
):
    """
    Initialize the optimized TWS client.
    
    Args:
        hostname: TWS server hostname
        port: TWS server port
        username: TWS username
        password: TWS password
        engine_name: TWS engine name
        engine_owner: TWS engine owner
    """
```

#### Key Methods

##### `async check_connection() -> bool`
- **Description**: Verifies the connection to the TWS server
- **Returns**: True if connection is active, False otherwise
- **Implementation**: Uses `/plan/current` endpoint

##### `async get_workstations_status() -> List[WorkstationStatus]`
- **Description**: Retrieves the status of all workstations
- **Returns**: List of workstation status objects
- **Features**: 
  - Caching enabled for performance
  - Automatic cache invalidation
- **Cache Key**: `"workstations_status"`

##### `async get_jobs_status() -> List[JobStatus]`
- **Description**: Retrieves the status of all jobs
- **Returns**: List of job status objects
- **Features**: 
  - Caching enabled for performance
  - Automatic cache invalidation
- **Cache Key**: `"jobs_status"`

##### `async get_critical_path_status() -> List[CriticalJob]`
- **Description**: Retrieves the status of jobs in the critical path
- **Returns**: List of critical job objects
- **Features**: 
  - Caching enabled for performance
  - Automatic cache invalidation
- **Cache Key**: `"critical_path_status"`

##### `async get_system_status() -> SystemStatus`
- **Description**: Retrieves comprehensive system status
- **Returns**: Complete system status object
- **Features**: Combines all status endpoints

#### Internal Methods

##### `@http_retry(max_attempts=3, min_wait=1.0, max_wait=5.0)`
- **Description**: Decorator for HTTP requests with retry logic
- **Features**: Exponential backoff retry strategy

##### `async _make_request(method: str, url: str, **kwargs: Any) -> httpx.Response`
- **Description**: Makes an HTTP request with retry logic
- **Parameters**:
  - `method`: HTTP method
  - `url`: Request URL
  - `**kwargs`: Additional request parameters
- **Returns**: HTTP response object
- **Features**: Automatic retry with exponential backoff

##### `async _api_request(method: str, url: str, **kwargs: Any) -> AsyncGenerator[Any, None]`
- **Description**: Context manager for making robust API requests
- **Parameters**:
  - `method`: HTTP method
  - `url`: Request URL
  - `**kwargs`: Additional request parameters
- **Returns**: Async generator yielding JSON response
- **Features**: Comprehensive error handling

### ConnectionManager

Service for managing WebSocket connections.

#### Constructor
```python
def __init__(self) -> None:
    """Initializes the ConnectionManager with an empty list of connections."""
```

#### Key Methods

##### `async connect(websocket: WebSocket) -> None`
- **Description**: Accepts a new WebSocket connection
- **Parameters**: `websocket` - The WebSocket connection to accept
- **Features**: Automatic connection acceptance and logging

##### `async disconnect(websocket: WebSocket) -> None`
- **Description**: Removes a WebSocket connection
- **Parameters**: `websocket` - The WebSocket connection to remove
- **Features**: Safe removal with logging

##### `async broadcast(message: str) -> None`
- **Description**: Sends a message to all connected clients
- **Parameters**: `message` - The message to broadcast
- **Features**: 
  - Concurrent message sending
  - Error handling for disconnected clients
  - Comprehensive logging

##### `async broadcast_json(data: Dict[str, Any]) -> None`
- **Description**: Sends JSON data to all connected clients
- **Parameters**: `data` - The JSON data to broadcast
- **Features**: 
  - Concurrent JSON sending
  - Error handling for disconnected clients
  - JSON serialization error handling

### AsyncTTLCache

Truly asynchronous TTL cache for optimal performance.

#### Constructor
```python
def __init__(
    self, 
    ttl_seconds: int = 60, 
    cleanup_interval: int = 30, 
    num_shards: int = 16
):
    """
    Initialize the async cache.
    
    Args:
        ttl_seconds: Time-to-live for cache entries in seconds
        cleanup_interval: How often to run background cleanup in seconds
        num_shards: Number of shards for the lock
    """
```

#### Key Methods

##### `async get(key: str) -> Any | None`
- **Description**: Asynchronously retrieve an item from the cache
- **Parameters**: `key` - Cache key to retrieve
- **Returns**: Cached value if exists and not expired, None otherwise
- **Features**: 
  - Thread-safe concurrent access
  - Automatic expiration handling

##### `async set(key: str, value: Any, ttl_seconds: Optional[int] = None) -> None`
- **Description**: Asynchronously add an item to the cache
- **Parameters**:
  - `key` - Cache key
  - `value` - Value to cache
  - `ttl_seconds` - Optional TTL override for this specific entry
- **Features**: 
  - Thread-safe concurrent access
  - Configurable TTL per entry

##### `async delete(key: str) -> bool`
- **Description**: Asynchronously delete an item from the cache
- **Parameters**: `key` - Cache key to delete
- **Returns**: True if item was deleted, False if not found
- **Features**: Thread-safe concurrent access

##### `async clear() -> None`
- **Description**: Asynchronously clear all cache entries
- **Features**: Thread-safe concurrent access

##### `async stop() -> None`
- **Description**: Stop the background cleanup task
- **Features**: Graceful shutdown with task cancellation

#### Internal Methods

##### `_get_shard(key: str) -> Tuple[Dict[str, CacheEntry], asyncio.Lock]`
- **Description**: Get the shard and lock for a given key
- **Parameters**: `key` - Cache key
- **Returns**: Tuple of shard dictionary and lock
- **Features**: Consistent sharding based on key hash

##### `_start_cleanup_task() -> None`
- **Description**: Start the background cleanup task
- **Features**: Automatic startup if not already running

##### `async _cleanup_expired_entries() -> None`
- **Description**: Background task to cleanup expired entries
- **Features**: 
  - Continuous cleanup loop
  - Comprehensive error handling
  - Graceful cancellation support

##### `async _remove_expired_entries() -> None`
- **Description**: Remove expired entries from cache
- **Features**: 
  - Thread-safe removal
  - Performance logging
  - Batch processing

## Data Models

### Core Models

#### AgentConfig
```python
class AgentConfig(BaseModel):
    """Represents the configuration for a single AI agent."""
    
    id: str
    name: str
    role: str
    goal: str
    backstory: str
    tools: List[str]
    model_name: str = "llama3:latest"
    memory: bool = True
    verbose: bool = False
```

#### AgentsConfig
```python
class AgentsConfig(BaseModel):
    """Represents the top-level structure of the agent configuration file."""
    
    agents: List[AgentConfig]
```

### TWS Models

#### WorkstationStatus
```python
class WorkstationStatus(BaseModel):
    """Represents the status of a single TWS workstation."""
    
    name: str = Field(..., description="The name of the workstation.")
    status: str = Field(
        ...,
        description="The current status of the workstation (e.g., 'LINKED', 'DOWN').",
    )
    type: str = Field(
        ..., description="The type of the workstation (e.g., 'FTA', 'MASTER')."
    )
```

#### JobStatus
```python
class JobStatus(BaseModel):
    """Represents the status of a single TWS job."""
    
    name: str = Field(..., description="The name of the job.")
    workstation: str = Field(..., description="The workstation where the job runs.")
    status: str = Field(
        ...,
        description="The current status of the job (e.g., 'SUCC', 'ABEND').",
    )
    job_stream: str = Field(..., description="The job stream the job belongs to.")
```

#### CriticalJob
```python
class CriticalJob(BaseModel):
    """Represents a job that is part of the critical path (TWS 'plan')."""
    
    job_id: int = Field(
        ..., description="The unique identifier for the job in the plan."
    )
    job_name: str = Field(..., description="The name of the job.")
    status: str = Field(..., description="The status of the critical job.")
    start_time: str = Field(..., description="The scheduled start time for the job.")
```

#### SystemStatus
```python
class SystemStatus(BaseModel):
    """A composite model representing the overall status of the TWS environment."""
    
    workstations: List[WorkstationStatus]
    jobs: List[JobStatus]
    critical_jobs: List[CriticalJob]
```

### Request/Response Models

#### ReviewAction
```python
class ReviewAction(BaseModel):
    """Represents a human review action for flagged memories."""
    
    memory_id: str
    action: str  # "approve" or "reject"
```

#### ReviewRequest
```python
class ReviewRequest(BaseModel):
    """Represents a review request for input validation testing."""
    
    content: str = Field(..., max_length=1000)
```

#### ExecuteRequest
```python
class ExecuteRequest(BaseModel):
    """Represents an execute request for command validation testing."""
    
    command: str
```

### Cache Models

#### CacheEntry
```python
@dataclass
class CacheEntry:
    """Represents a single entry in the cache with timestamp and TTL."""
    
    data: Any
    timestamp: float
    ttl: float
```

### Knowledge Graph Models

#### MemoryConfig
```python
class MemoryConfig(BaseModel):
    """Configuration for the async Mem0 client."""
    
    storage_provider: str = "qdrant"
    storage_host: str = "localhost"
    storage_port: int = 6333
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
```

## Exception Handling

### Core Exceptions

#### ConfigError
```python
class ConfigError(Exception):
    """Raised when there's a configuration-related error."""
    pass
```

#### AgentError
```python
class AgentError(Exception):
    """Raised when there's an agent-related error."""
    pass
```

#### FileProcessingError
```python
class FileProcessingError(Exception):
    """Raised when there's a file processing error."""
    pass
```

#### KnowledgeGraphError
```python
class KnowledgeGraphError(Exception):
    """Raised when there's a knowledge graph error."""
    pass
```

#### NetworkError
```python
class NetworkError(Exception):
    """Raised when there's a network-related error."""
    pass
```

#### WebSocketError
```python
class WebSocketError(Exception):
    """Raised when there's a WebSocket-related error."""
    pass
```

#### CacheError
```python
class CacheError(Exception):
    """Raised when there's a cache-related error."""
    pass
```

### Specific Exceptions

#### MissingConfigError
```python
class MissingConfigError(ConfigError):
    """Raised when a required configuration is missing."""
    pass
```

#### InvalidConfigError
```python
class InvalidConfigError(ConfigError):
    """Raised when a configuration is invalid."""
    pass
```

#### DataParsingError
```python
class DataParsingError(Exception):
    """Raised when there's a data parsing error."""
    pass
```

#### ProcessingError
```python
class ProcessingError(Exception):
    """Raised when there's a processing error."""
    pass
```

#### AuditError
```python
class AuditError(Exception):
    """Raised when there's an audit-related error."""
    pass
```

#### DatabaseError
```python
class DatabaseError(Exception):
    """Raised when there's a database-related error."""
    pass
```

## Configuration

### Settings Structure

The application uses environment-based configuration with the following structure:

```python
# Development Settings
class DevelopmentSettings(BaseSettings):
    # Application
    PROJECT_NAME: str = "Resync"
    PROJECT_VERSION: str = "0.1.0"
    DESCRIPTION: str = "AI-powered TWS management system"
    
    # TWS Configuration
    TWS_HOST: str = "localhost"
    TWS_PORT: int = 31116
    TWS_USER: str = "twsuser"
    TWS_PASSWORD: str = "twspass"
    TWS_ENGINE_NAME: str = "tws-engine"
    TWS_ENGINE_OWNER: str = "tws-owner"
    TWS_MOCK_MODE: bool = True
    TWS_CACHE_TTL: int = 300
    
    # Knowledge Graph Configuration
    MEM0_STORAGE_HOST: str = "localhost"
    MEM0_STORAGE_PORT: int = 6333
    MEM0_EMBEDDING_PROVIDER: str = "openai"
    MEM0_EMBEDDING_MODEL: str = "text-embedding-3-small"
    MEM0_LLM_PROVIDER: str = "openai"
    MEM0_LLM_MODEL: str = "gpt-4o-mini"
    
    # File Processing
    RAG_DIRECTORY: str = "rag"
    
    # Agent Configuration
    AGENT_CONFIG_PATH: Path = Path("agents.json")
    
    # Base Directory
    BASE_DIR: Path = Path(__file__).parent.parent
```

### Environment Variables

The application supports the following environment variables:

- `APP_ENV`: Application environment (development/production)
- `TWS_HOST`: TWS server hostname
- `TWS_PORT`: TWS server port
- `TWS_USER`: TWS username
- `TWS_PASSWORD`: TWS password
- `TWS_ENGINE_NAME`: TWS engine name
- `TWS_ENGINE_OWNER`: TWS engine owner
- `TWS_MOCK_MODE`: Enable mock mode for testing
- `MEM0_STORAGE_HOST`: Mem0 storage host
- `MEM0_STORAGE_PORT`: Mem0 storage port
- `MEM0_EMBEDDING_PROVIDER`: Embedding provider
- `MEM0_EMBEDDING_MODEL`: Embedding model
- `MEM0_LLM_PROVIDER`: LLM provider
- `MEM0_LLM_MODEL`: LLM model

### Configuration Files

#### Agent Configuration (`agents.json`)
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
    }
  ]
}
```

This comprehensive component reference provides detailed information about all the core components, their interfaces, implementations, and configuration options in the Resync system.


