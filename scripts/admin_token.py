#!/usr/bin/env python3
"""Admin CLI for token management"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth.token_verifier import AdminTokenVerifier
from src.config import config


def generate_token(args):
    """Generate a new token for a user"""
    verifier = AdminTokenVerifier(config.TOKEN_SECRET_KEY, config.TOKENS_FILE)

    scopes = args.scopes.split(",") if args.scopes else ["usage:write"]
    token = verifier.generate_token(args.user_id, scopes)

    print(f"\n✅ Token generated successfully for: {args.user_id}")
    print(f"\nToken: {token}")
    print(f"\nScopes: {', '.join(scopes)}")
    print(
        f"\n⚠️  Share this token securely with {args.user_id}. They should add it to their environment:"
    )
    print(f'\nexport MCP_USAGE_ACCESS_TOKEN="{token}"')
    print()


def revoke_token(args):
    """Revoke a token"""
    verifier = AdminTokenVerifier(config.TOKEN_SECRET_KEY, config.TOKENS_FILE)

    success = verifier.revoke_token(args.token)

    if success:
        print(f"\n✅ Token revoked successfully: {args.token[:20]}...")
    else:
        print(f"\n❌ Token not found: {args.token[:20]}...")
    print()


def list_tokens(args):
    """List all tokens"""
    verifier = AdminTokenVerifier(config.TOKEN_SECRET_KEY, config.TOKENS_FILE)

    tokens = verifier.list_tokens(include_revoked=args.include_revoked)

    if not tokens:
        print("\n📭 No tokens found.")
        if not args.include_revoked:
            print("   Use --include-revoked to see revoked tokens.")
        print()
        return

    print(f"\n📋 Tokens ({len(tokens)} total):\n")
    print(f"{'Token (preview)':<25} {'User ID':<20} {'Status':<10} {'Created At'}")
    print("-" * 80)

    for token in tokens:
        token_preview = f"{token['token'][:22]}..."
        status = "🔴 REVOKED" if token["revoked"] else "🟢 ACTIVE"
        created = token["created_at"] or "N/A"

        print(f"{token_preview:<25} {token['user_id']:<20} {status:<10} {created}")

    print()


def info(args):
    """Show configuration info"""
    print("\n⚙️  Configuration:\n")
    print(f"Server URL:      {config.SERVER_URL}")
    print(f"Auth Issuer:     {config.AUTH_ISSUER_URL}")
    print(f"Token Registry:  {config.TOKENS_FILE}")
    print(f"Langfuse Host:   {config.LANGFUSE_HOST}")

    if config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY:
        print(f"Langfuse:        ✅ Configured")
    else:
        print(f"Langfuse:        ⚠️  Not configured")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Admin CLI for MCP Ops AI Use Monitor token management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Generate token command
    gen_parser = subparsers.add_parser("generate", help="Generate a new token for a user")
    gen_parser.add_argument("user_id", help="GitHub username of the user")
    gen_parser.add_argument(
        "--scopes", help='Comma-separated scopes (default: "usage:write")', default=None
    )

    # Revoke token command
    revoke_parser = subparsers.add_parser("revoke", help="Revoke an existing token")
    revoke_parser.add_argument("token", help="Token to revoke")

    # List tokens command
    list_parser = subparsers.add_parser("list", help="List all tokens")
    list_parser.add_argument(
        "--include-revoked", action="store_true", help="Include revoked tokens"
    )

    # Info command
    info_parser = subparsers.add_parser("info", help="Show configuration info")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "generate":
        generate_token(args)
    elif args.command == "revoke":
        revoke_token(args)
    elif args.command == "list":
        list_tokens(args)
    elif args.command == "info":
        info(args)


if __name__ == "__main__":
    main()
