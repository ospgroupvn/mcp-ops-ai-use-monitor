"""Data models for usage tracking"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a single tool call in the session"""

    id: str = Field(..., description="Tool call ID")
    name: str = Field(..., description="Tool name (e.g., Read, Bash, Edit)")
    input: dict = Field(default_factory=dict, description="Tool input parameters")


class UsageContext(BaseModel):
    """Context information for a single prompt usage"""

    input_tokens: int = Field(..., description="Number of input tokens", ge=0)
    output_tokens: int = Field(..., description="Number of output tokens", ge=0)
    model: str = Field(..., description="Model used (e.g., claude-sonnet-4-20250514)")
    duration_ms: int = Field(..., description="Processing duration in milliseconds", ge=0)

    @property
    def total_tokens(self) -> int:
        """Total tokens used"""
        return self.input_tokens + self.output_tokens


class UsageData(BaseModel):
    """Complete usage data for a Claude Code prompt session"""

    user_prompt: str = Field(..., description="User's prompt content")
    assistant_response: str = Field(..., description="Assistant's response")
    context: UsageContext = Field(..., description="Usage context information")
    github_username: str = Field(..., description="GitHub username from git config")
    session_id: str = Field(..., description="Claude Code session ID")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of the usage"
    )
    project_name: Optional[str] = Field(None, description="Project name (directory name)")
    tool_calls: List[ToolCall] = Field(
        default_factory=list, description="List of tool calls in this session"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_prompt": "Create a function to calculate fibonacci",
                "assistant_response": "Here's a fibonacci function...",
                "context": {
                    "input_tokens": 150,
                    "output_tokens": 200,
                    "model": "claude-sonnet-4-20250514",
                    "duration_ms": 2500,
                },
                "github_username": "john_doe",
                "session_id": "sess_abc123",
                "project_name": "my-project",
            }
        }
