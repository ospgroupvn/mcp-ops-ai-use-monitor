#!/usr/bin/env python3
"""Test UsageTracer with real data"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.langfuse.tracer import UsageTracer
from src.models.usage_data import UsageData, UsageContext

def test_usage_tracer():
    """Test creating a usage trace"""
    print("🔍 Testing UsageTracer...\n")

    try:
        # Create test usage data
        usage = UsageData(
            user_prompt="Create a hello world function in Python",
            assistant_response="Here's a hello world function:\n\ndef hello():\n    print('Hello, World!')",
            context=UsageContext(
                input_tokens=120,
                output_tokens=85,
                model="claude-sonnet-4-20250514",
                duration_ms=2500
            ),
            github_username="test-user",
            session_id="test-session-123",
            project_name="mcp-ops-ai-use-monitor",
            timestamp=datetime.utcnow()
        )

        print(f"Test data created:")
        print(f"  User: {usage.github_username}")
        print(f"  Project: {usage.project_name}")
        print(f"  Tokens: {usage.context.input_tokens} + {usage.context.output_tokens} = {usage.context.total_tokens}")
        print()

        # Create tracer and send usage
        print("Creating tracer and sending to Langfuse...")
        tracer = UsageTracer()

        trace_id = tracer.trace_usage(usage)
        tracer.flush()

        print(f"✅ Successfully sent to Langfuse!")
        print(f"✅ Trace ID: {trace_id}")
        print(f"\nView trace at: https://langfuse.ospgroup.io.vn")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_usage_tracer()
    sys.exit(0 if success else 1)
