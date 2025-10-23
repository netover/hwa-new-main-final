"""Agent validation models with strict validation rules."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator, validator
from pydantic.types import constr

from .common import NumericConstraints, StringConstraints, ValidationPatterns


class AgentType(str, Enum):
    """Valid agent types."""

    LOCAL_SCRIPT = "local_script"
    EXTERNAL_API = "external_api"
    DATABASE_QUERY = "database_query"
    TWS_SPECIALIST = "tws_specialist"
    GENERAL_ASSISTANT = "general_assistant"


class AgentStatus(str, Enum):
    """Agent status values."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class ToolCategory(str, Enum):
    """Valid tool categories."""

    TWS_TOOLS = "tws_tools"
    DATABASE_TOOLS = "database_tools"
    API_TOOLS = "api_tools"
    UTILITY_TOOLS = "utility_tools"
    MONITORING_TOOLS = "monitoring_tools"


class AgentConfig(BaseModel):
    """Agent configuration validation model."""

    id: StringConstraints.AGENT_ID = Field(
        ..., description="Unique agent identifier", example="tws-troubleshooter-01"
    )

    name: constr(
        min_length=NumericConstraints.MIN_AGENT_NAME_LENGTH,
        max_length=NumericConstraints.MAX_AGENT_NAME_LENGTH,
        strip_whitespace=True,
    ) = Field(
        ...,
        description="Human-readable agent name",
        example="TWS Troubleshooting Agent",
    )

    role: StringConstraints.ROLE_TEXT = Field(
        ...,
        description="Agent's role description",
        example="Specialized in TWS system troubleshooting and diagnostics",
    )

    goal: StringConstraints.ROLE_TEXT = Field(
        ...,
        description="Primary goal of the agent",
        example="Resolve TWS system issues and provide diagnostic assistance",
    )

    backstory: StringConstraints.ROLE_TEXT = Field(
        ...,
        description="Agent's background story",
        example="An experienced TWS administrator with deep system knowledge",
    )

    tools: list[StringConstraints.TOOL_NAME] = Field(
        default_factory=list,
        description="List of tools the agent can use",
        max_length=20,
        example=["tws_status_tool", "tws_troubleshooting_tool"],
    )

    model_name: StringConstraints.MODEL_NAME = Field(
        default="llama3:latest", description="LLM model name", example="llama3:latest"
    )

    memory: bool = Field(
        default=True, description="Whether the agent has memory enabled"
    )

    verbose: bool = Field(
        default=False, description="Whether the agent operates in verbose mode"
    )

    type: AgentType = Field(
        default=AgentType.TWS_SPECIALIST, description="Type of agent"
    )

    status: AgentStatus = Field(
        default=AgentStatus.ACTIVE, description="Current agent status"
    )

    description: Optional[
        constr(
            min_length=NumericConstraints.MIN_AGENT_DESCRIPTION_LENGTH,
            max_length=NumericConstraints.MAX_AGENT_DESCRIPTION_LENGTH,
            strip_whitespace=True,
        )
    ] = Field(None, description="Detailed agent description")

    configuration: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional agent configuration",
        max_length=50,
    )

    tags: list[constr(min_length=1, max_length=50)] = Field(
        default_factory=list, description="Agent tags for categorization", max_length=10
    )

    max_tokens: Optional[int] = Field(
        None, ge=100, le=100000, description="Maximum tokens for model responses"
    )

    temperature: Optional[float] = Field(
        None, ge=0.0, le=2.0, description="Model temperature setting"
    )

    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        extra="forbid",
    )

    @validator("name")
    def validate_agent_name(cls, v: str) -> str:
        """Validate agent name doesn't contain malicious content."""
        if ValidationPatterns.SCRIPT_PATTERN.search(v):
            raise ValueError("Agent name contains potentially malicious content")
        if ValidationPatterns.COMMAND_INJECTION_PATTERN.search(v):
            raise ValueError("Agent name contains invalid characters")
        return v

    @validator("role", "goal", "backstory", "description")
    def validate_text_content(cls, v: str | None) -> str | None:
        """Validate text fields for malicious content."""
        if v and ValidationPatterns.SCRIPT_PATTERN.search(v):
            raise ValueError("Text contains potentially malicious content")
        return v

    @validator("tools")
    def validate_tools_list(cls, v: list[str] | None) -> list[str] | None:
        """Validate tools list."""
        if not v:
            return v
        # Check for duplicate tools
        if len(v) != len(set(v)):
            raise ValueError("Duplicate tools found in list")
        # Validate each tool name
        for tool in v:
            if not tool.replace("_", "").replace("-", "").isalnum():
                raise ValueError(f"Invalid tool name: {tool}")
        return v

    @validator("tags")
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        """Validate tags list."""
        if not v:
            return v
        # Check for duplicate tags
        if len(v) != len(set(v)):
            raise ValueError("Duplicate tags found in list")
        # Validate each tag
        for tag in v:
            if not tag.replace("-", "").replace("_", "").isalnum():
                raise ValueError(f"Invalid tag format: {tag}")
        return v

    @model_validator(mode="before")
    def validate_model_compatibility(cls, values):
        """Validate model compatibility with configuration."""
        if isinstance(values, dict):
            model_name = values.get("model_name")
            max_tokens = values.get("max_tokens")
            if model_name and max_tokens:
                # Add model-specific token limits here
                model_limits = {
                    "llama3:latest": 8192,
                    "gpt-3.5-turbo": 4096,
                    "gpt-4": 8192,
                }
                if model_name in model_limits and max_tokens > model_limits[model_name]:
                    raise ValueError(
                        f"Max tokens {max_tokens} exceeds limit for {model_name} "
                        f"(max: {model_limits[model_name]})"
                    )
        return values


class AgentCreateRequest(AgentConfig):
    """Request model for creating a new agent."""

    model_config = ConfigDict(
        extra="forbid",
    )

    @model_validator(mode="before")
    def validate_create_request(cls, values):
        """Validate agent creation request."""
        if isinstance(values, dict):
            # Ensure required fields are provided
            required_fields = ["id", "name", "role", "goal", "backstory"]
            for field in required_fields:
                if not values.get(field):
                    raise ValueError(f"Required field '{field}' is missing or empty")
        return values


class AgentUpdateRequest(BaseModel):
    """Request model for updating an existing agent."""

    name: Optional[
        constr(
            min_length=NumericConstraints.MIN_AGENT_NAME_LENGTH,
            max_length=NumericConstraints.MAX_AGENT_NAME_LENGTH,
            strip_whitespace=True,
        )
    ] = Field(None, description="Updated agent name")

    role: Optional[StringConstraints.ROLE_TEXT] = Field(
        None, description="Updated agent role"
    )

    goal: Optional[StringConstraints.ROLE_TEXT] = Field(
        None, description="Updated agent goal"
    )

    backstory: Optional[StringConstraints.ROLE_TEXT] = Field(
        None, description="Updated agent backstory"
    )

    tools: Optional[list[StringConstraints.TOOL_NAME]] = Field(
        None, description="Updated tools list", max_length=20
    )

    model_name: Optional[StringConstraints.MODEL_NAME] = Field(
        None, description="Updated model name"
    )

    memory: Optional[bool] = Field(None, description="Updated memory setting")

    verbose: Optional[bool] = Field(None, description="Updated verbose setting")

    type: Optional[AgentType] = Field(None, description="Updated agent type")

    status: Optional[AgentStatus] = Field(None, description="Updated agent status")

    description: Optional[
        constr(
            min_length=NumericConstraints.MIN_AGENT_DESCRIPTION_LENGTH,
            max_length=NumericConstraints.MAX_AGENT_DESCRIPTION_LENGTH,
            strip_whitespace=True,
        )
    ] = Field(None, description="Updated agent description")

    configuration: Optional[dict[str, Any]] = Field(
        None, description="Updated configuration", max_length=50
    )

    tags: Optional[list[constr(min_length=1, max_length=50)]] = Field(
        None, description="Updated tags", max_length=10
    )

    max_tokens: Optional[int] = Field(
        None, ge=100, le=100000, description="Updated max tokens"
    )

    temperature: Optional[float] = Field(
        None, ge=0.0, le=2.0, description="Updated temperature"
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    @validator("name", "role", "goal", "backstory", "description")
    def validate_text_content(cls, v):
        """Validate text fields for malicious content."""
        if v and ValidationPatterns.SCRIPT_PATTERN.search(v):
            raise ValueError("Text contains potentially malicious content")
        return v

    @validator("tools")
    def validate_tools_list(cls, v):
        """Validate tools list if provided."""
        if v is None:
            return v
        if not v:
            return v
        # Check for duplicate tools
        if len(v) != len(set(v)):
            raise ValueError("Duplicate tools found in list")
        # Validate each tool name
        for tool in v:
            if not tool.replace("_", "").replace("-", "").isalnum():
                raise ValueError(f"Invalid tool name: {tool}")
        return v

    @validator("tags")
    def validate_tags(cls, v):
        """Validate tags list if provided."""
        if v is None:
            return v
        if not v:
            return v
        # Check for duplicate tags
        if len(v) != len(set(v)):
            raise ValueError("Duplicate tags found in list")
        # Validate each tag
        for tag in v:
            if not tag.replace("-", "").replace("_", "").isalnum():
                raise ValueError(f"Invalid tag format: {tag}")
        return v


class AgentQueryParams(BaseModel):
    """Query parameters for agent-related endpoints."""

    agent_id: Optional[StringConstraints.AGENT_ID] = Field(
        None, description="Filter by specific agent ID"
    )

    name: Optional[constr(min_length=1, max_length=100)] = Field(
        None, description="Filter by agent name (partial match)"
    )

    type: Optional[AgentType] = Field(None, description="Filter by agent type")

    status: Optional[AgentStatus] = Field(None, description="Filter by agent status")

    tags: Optional[list[constr(min_length=1, max_length=50)]] = Field(
        None, description="Filter by tags", max_length=5
    )

    include_inactive: bool = Field(
        default=False, description="Include inactive agents in results"
    )

    sort_by: Optional[str] = Field(
        default="name",
        pattern=r"^(name|id|type|status|created_at|updated_at)$",
        description="Field to sort results by",
    )

    sort_order: Optional[str] = Field(
        default="asc",
        pattern=r"^(asc|desc)$",
        description="Sort order (ascending or descending)",
    )

    model_config = ConfigDict(
        extra="forbid",
    )

    @validator("tags")
    def validate_tags(cls, v):
        """Validate tags list."""
        if not v:
            return v
        # Check for duplicate tags
        if len(v) != len(set(v)):
            raise ValueError("Duplicate tags found in list")
        return v


class AgentBulkActionRequest(BaseModel):
    """Request model for bulk agent operations."""

    agent_ids: list[StringConstraints.AGENT_ID] = Field(
        ...,
        description="List of agent IDs to perform action on",
        min_length=1,
        max_length=100,
    )

    action: str = Field(
        ...,
        pattern=r"^(activate|deactivate|delete|export)$",
        description="Bulk action to perform",
    )

    confirmation_token: Optional[str] = Field(
        None, description="Confirmation token for destructive actions"
    )

    model_config = ConfigDict(
        extra="forbid",
    )

    @validator("agent_ids")
    def validate_agent_ids(cls, v):
        """Validate agent IDs list."""
        if not v:
            raise ValueError("Agent IDs list cannot be empty")
        # Check for duplicate IDs
        if len(v) != len(set(v)):
            raise ValueError("Duplicate agent IDs found in list")
        return v
