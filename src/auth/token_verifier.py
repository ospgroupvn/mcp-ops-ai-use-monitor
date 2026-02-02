"""Token verification and management"""

import hashlib
import hmac
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp.server.auth.provider import AccessToken, TokenVerifier


class AdminTokenVerifier(TokenVerifier):
    """
    Token verifier for admin-issued access tokens.

    Token format: {user_id}:{timestamp}:{signature}
    Tokens are stored in a JSON registry file with metadata.
    """

    def __init__(self, secret_key: str, tokens_file: Path):
        """
        Initialize token verifier.

        Args:
            secret_key: Secret key for token signature verification
            tokens_file: Path to JSON file containing token registry
        """
        self.secret_key = secret_key
        self.tokens_file = tokens_file
        self._tokens_cache: Optional[dict] = None

    def _load_tokens(self) -> dict:
        """Load tokens from registry file"""
        if not self.tokens_file.exists():
            return {}

        try:
            with open(self.tokens_file, "r") as f:
                data = json.load(f)
                return data.get("tokens", {})
        except Exception as e:
            print(f"Error loading tokens: {e}")
            return {}

    def _save_tokens(self, tokens: dict):
        """Save tokens to registry file"""
        try:
            self.tokens_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.tokens_file, "w") as f:
                json.dump({"tokens": tokens}, f, indent=2)
            self._tokens_cache = None  # Invalidate cache
        except Exception as e:
            print(f"Error saving tokens: {e}")

    def _get_tokens(self) -> dict:
        """Get tokens with caching"""
        if self._tokens_cache is None:
            self._tokens_cache = self._load_tokens()
        return self._tokens_cache

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """
        Verify access token.

        Args:
            token: Token string to verify

        Returns:
            AccessToken if valid, None otherwise
        """
        tokens = self._get_tokens()

        # Check if token exists in registry
        if token not in tokens:
            return None

        token_info = tokens[token]

        # Check if token is revoked
        if token_info.get("revoked", False):
            return None

        # Check expiration
        expires_at_str = token_info.get("expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.utcnow() > expires_at:
                    return None
            except Exception:
                pass

        return AccessToken(
            token=token,
            scopes=token_info.get("scopes", ["usage:write"]),
            expires_at=None,  # MCP AccessToken expects None or int timestamp
            client_id=token_info.get("user_id"),
        )

    def generate_token(self, user_id: str, scopes: Optional[list[str]] = None) -> str:
        """
        Generate new access token for a user.

        Args:
            user_id: User identifier (GitHub username)
            scopes: List of permission scopes

        Returns:
            Generated token string
        """
        if scopes is None:
            scopes = ["usage:write"]

        timestamp = int(datetime.utcnow().timestamp())
        payload = f"{user_id}:{timestamp}"

        # Generate HMAC signature
        signature = hmac.new(
            self.secret_key.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()[:16]

        token = f"{payload}:{signature}"

        # Save to registry
        tokens = self._get_tokens()
        tokens[token] = {
            "user_id": user_id,
            "scopes": scopes,
            "revoked": False,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": None,
        }
        self._save_tokens(tokens)

        return token

    def revoke_token(self, token: str) -> bool:
        """
        Revoke an access token.

        Args:
            token: Token to revoke

        Returns:
            True if token was revoked, False if not found
        """
        tokens = self._get_tokens()

        if token not in tokens:
            return False

        tokens[token]["revoked"] = True
        tokens[token]["revoked_at"] = datetime.utcnow().isoformat()
        self._save_tokens(tokens)

        return True

    def list_tokens(self, include_revoked: bool = False) -> list[dict]:
        """
        List all tokens.

        Args:
            include_revoked: Whether to include revoked tokens

        Returns:
            List of token info dictionaries
        """
        tokens = self._get_tokens()
        result = []

        for token, info in tokens.items():
            if not include_revoked and info.get("revoked", False):
                continue

            result.append(
                {
                    "token": token,
                    "user_id": info.get("user_id"),
                    "scopes": info.get("scopes", []),
                    "revoked": info.get("revoked", False),
                    "created_at": info.get("created_at"),
                    "expires_at": info.get("expires_at"),
                }
            )

        return result
