#!/usr/bin/env python3
"""Test Langfuse connection"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from langfuse import Langfuse

def test_langfuse_connection():
    """Test connection to Langfuse"""
    print("🔍 Testing Langfuse connection...\n")

    print(f"Host: {config.LANGFUSE_HOST}")
    print(f"Public Key: {config.LANGFUSE_PUBLIC_KEY[:20]}...")
    print(f"Secret Key: {config.LANGFUSE_SECRET_KEY[:20]}...\n")

    try:
        # Initialize Langfuse client
        langfuse = Langfuse(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            host=config.LANGFUSE_HOST
        )

        # Try to create a generation (simpler test)
        print("Attempting to connect...")

        # Create a test generation
        generation = langfuse.generation(
            name="test-connection",
            model="test",
            input="test input",
            output="test output"
        )

        langfuse.flush()

        print("✅ Successfully connected to Langfuse!")
        print(f"✅ Test generation created with ID: {generation.id}")

        return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = test_langfuse_connection()
    sys.exit(0 if success else 1)
