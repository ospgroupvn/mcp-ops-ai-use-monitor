"""Langfuse integration for usage tracing"""

from typing import Optional

# Import from langfuse package, not local module
try:
    from langfuse import Langfuse
except ImportError:
    from langfuse._client.client import Langfuse

from ..config import config
from ..models.usage_data import UsageData


class UsageTracer:
    """
    Tracer for sending Claude Code usage data to Langfuse.

    Creates traces with user_id, session_id, and detailed generation information
    including token usage and model metadata.

    Uses Langfuse SDK v3 with context managers and span API.
    """

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
    ):
        """
        Initialize Langfuse tracer.

        Args:
            public_key: Langfuse public key (defaults to config)
            secret_key: Langfuse secret key (defaults to config)
            host: Langfuse host URL (defaults to config)
        """
        self.langfuse = Langfuse(
            public_key=public_key or config.LANGFUSE_PUBLIC_KEY,
            secret_key=secret_key or config.LANGFUSE_SECRET_KEY,
            host=host or config.LANGFUSE_HOST,
        )

    def trace_usage(
        self,
        usage: UsageData,
        repo_full_name: Optional[str] = None,
        repo_url: Optional[str] = None,
        message_count: int = 0,
    ) -> str:
        """
        Create a trace in Langfuse for a Claude Code usage event.

        Args:
            usage: UsageData object containing prompt, response, and metadata
            repo_full_name: Full repo name in owner/repo format (e.g., ospgroupvn/my-repo)
            repo_url: Full git remote URL
            message_count: Number of messages in the session

        Returns:
            trace_id: ID of the created trace
        """
        # Build metadata with repo info
        metadata = {
            "project_name": usage.project_name,
            "timestamp": usage.timestamp.isoformat(),
            "total_tokens": usage.context.total_tokens,
        }
        if repo_full_name:
            metadata["repo_full_name"] = repo_full_name
        if repo_url:
            metadata["repo_url"] = repo_url
        if message_count > 0:
            metadata["message_count"] = message_count
        if usage.tool_calls:
            metadata["tool_count"] = len(usage.tool_calls)

        # Build tags
        tags = ["claude-code", usage.context.model]
        if repo_full_name:
            tags.append(f"repo:{repo_full_name}")

        # Create main trace span using context manager (sets up trace context)
        with self.langfuse.start_as_current_span(
            name="claude-code-usage",
            input={"user_prompt": usage.user_prompt[:500]},
            output={"assistant_response": usage.assistant_response[:1000]},
            metadata=metadata,
        ):
            # Get trace ID for creating sibling spans later
            trace_id = self.langfuse.get_current_trace_id()

            # Update trace metadata
            self.langfuse.update_current_trace(
                user_id=usage.github_username,
                session_id=usage.session_id,
                tags=tags,
            )

            # Create generation span for LLM call
            with self.langfuse.start_as_current_generation(
                name="claude-code-generation",
                model=usage.context.model,
                input=usage.user_prompt[:500],
                output=usage.assistant_response[:1000],
                metadata={
                    "duration_ms": usage.context.duration_ms,
                    "project": usage.project_name,
                    "repo_full_name": repo_full_name,
                    "repo_url": repo_url,
                    "message_count": message_count,
                },
            ):
                # Update generation with usage details
                self.langfuse.update_current_generation(
                    usage_details={
                        "input": usage.context.input_tokens,
                        "output": usage.context.output_tokens,
                        "total": usage.context.total_tokens,
                    }
                )

        # Create tool spans as siblings (outside context manager)
        # Import TraceContext for creating tool spans attached to the trace
        from langfuse.types import TraceContext
        trace_context = TraceContext(trace_id=trace_id)

        for tool_call in usage.tool_calls:
            try:
                tool_span = self.langfuse.start_span(
                    name=f"tool:{tool_call.name}",
                    trace_context=trace_context,
                    input=tool_call.input,
                    metadata={
                        "tool_id": tool_call.id,
                        "tool_name": tool_call.name,
                    },
                )
                tool_span.end()
            except Exception as e:
                # Log but don't fail the entire trace if one tool span fails
                print(f"[langfuse] Warning: Failed to create tool span: {e}")

        return trace_id

    def flush(self):
        """Ensure all data is sent to Langfuse"""
        self.langfuse.flush()

    def shutdown(self):
        """Shutdown Langfuse client gracefully"""
        self.langfuse.shutdown()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic flush"""
        self.flush()
        return False
