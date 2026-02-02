#!/usr/bin/env python3
"""Test creating trace with Langfuse v3"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from langfuse import Langfuse

def test_create_trace():
    """Test creating a trace"""
    print("🔍 Testing trace creation...\n")

    try:
        langfuse = Langfuse(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            host=config.LANGFUSE_HOST,
            debug=True
        )

        # Check if trace method exists
        if hasattr(langfuse, 'trace'):
            print("✅ trace() method exists")
        else:
            print("❌ trace() method NOT found")
            print("Available methods:", [m for m in dir(langfuse) if not m.startswith('_')])
            return False

        # Try to create a trace using low-level API
        print("\nTrying to create trace using create_event...")

        event_id = langfuse.create_event(
            name="test-event",
            user_id="test-user",
            input="test input",
            output="test output",
            metadata={"test": True}
        )

        print(f"✅ Event created with ID: {event_id}")

        langfuse.flush()
        print("✅ Flushed successfully")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_create_trace()
    sys.exit(0 if success else 1)
