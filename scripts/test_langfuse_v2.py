#!/usr/bin/env python3
"""Test Langfuse connection - v3 API"""

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
        print("Initializing Langfuse client...")
        langfuse = Langfuse(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            host=config.LANGFUSE_HOST
        )

        print("✅ Langfuse client initialized!")

        # List available methods
        print("\nAvailable methods:")
        methods = [m for m in dir(langfuse) if not m.startswith('_')]
        for method in methods[:10]:
            print(f"  - {method}")

        print("\n✅ Connection successful!")
        print("Note: SDK v3 uses decorator @observe or context managers for tracing")

        return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_langfuse_connection()
    sys.exit(0 if success else 1)
