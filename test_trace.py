#!/usr/bin/env python3
"""Test script to verify Langfuse tracing with tool calls"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.models.usage_data import UsageData, UsageContext, ToolCall
from src.langfuse.tracer import UsageTracer


def main():
    print("Testing Langfuse tracing with tool calls...")

    # Create test data with tool calls
    usage = UsageData(
        user_prompt="Test prompt for checking tool calls",
        assistant_response="Test response",
        context=UsageContext(
            input_tokens=100,
            output_tokens=50,
            model="test-model",
            duration_ms=5000,
        ),
        github_username="test-user",
        session_id="test-session-123",
        project_name="test-repo",
        tool_calls=[
            ToolCall(id="tool-1", name="Read", input={"file_path": "/path/to/file.txt"}),
            ToolCall(id="tool-2", name="Bash", input={"command": "ls -la"}),
            ToolCall(id="tool-3", name="Write", input={"file_path": "/path/to/new.txt", "content": "hello"}),
        ],
    )

    # Create tracer
    tracer = UsageTracer()

    # Send trace
    trace_id = tracer.trace_usage(
        usage,
        repo_full_name="ospgroupvn/test-repo",
        repo_url="https://github.com/ospgroupvn/test-repo.git",
        message_count=10,
    )

    print(f"Trace created: {trace_id}")
    print(f"Tool calls sent: {len(usage.tool_calls)}")

    # Flush to ensure data is sent
    tracer.flush()

    print("Check Langfuse dashboard: https://langfuse.ospgroup.io.vn")
    print(f"Search for trace ID: {trace_id}")


if __name__ == "__main__":
    main()
