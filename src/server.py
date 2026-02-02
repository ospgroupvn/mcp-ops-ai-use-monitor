"""Main MCP Server for Claude Code Usage Monitoring"""

from typing import List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl

from .auth.token_verifier import AdminTokenVerifier
from .config import config
from .tracing.tracer import UsageTracer
from .models.usage_data import ToolCall, UsageContext, UsageData

# Initialize token verifier
token_verifier = AdminTokenVerifier(
    secret_key=config.TOKEN_SECRET_KEY, tokens_file=config.TOKENS_FILE
)

# Initialize Langfuse tracer
usage_tracer = UsageTracer()

# Initialize MCP Server with authentication
mcp = FastMCP(
    "osp-usage-monitor",
    json_response=True,
    token_verifier=token_verifier,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(config.AUTH_ISSUER_URL),
        resource_server_url=AnyHttpUrl(config.SERVER_URL),
        required_scopes=["usage:write"],
    ),
)


@mcp.tool()
async def report_usage(
    user_prompt: str,
    assistant_response: str,
    input_tokens: int,
    output_tokens: int,
    model: str,
    duration_ms: int,
    github_username: str,
    session_id: str,
    project_name: Optional[str] = None,
    repo_full_name: Optional[str] = None,
    repo_url: Optional[str] = None,
    message_count: int = 0,
    tool_calls: Optional[List[dict]] = None,
) -> dict:
    """
    Report Claude Code usage data and send to Langfuse.

    This tool receives usage information from Claude Code hooks and creates
    a trace in Langfuse for observability and analytics.

    Args:
        user_prompt: The user's prompt content
        assistant_response: Claude's response content
        input_tokens: Number of input tokens used (from last message only)
        output_tokens: Number of output tokens generated
        model: Model identifier (e.g., claude-sonnet-4-20250514)
        duration_ms: Processing duration in milliseconds
        github_username: GitHub username from git config
        session_id: Claude Code session ID
        project_name: Project repository name (e.g., my-repo)
        repo_full_name: Full repo name in owner/repo format (e.g., ospgroupvn/my-repo)
        repo_url: Full git remote URL
        message_count: Number of messages in the session
        tool_calls: List of tool calls made during the session

    Returns:
        dict: Status and trace information
    """
    import sys

    try:
        # Parse tool calls if provided
        parsed_tool_calls = []
        if tool_calls:
            for tc in tool_calls:
                try:
                    parsed_tool_calls.append(
                        ToolCall(
                            id=tc.get("id", ""),
                            name=tc.get("name", "unknown"),
                            input=tc.get("input", {}),
                        )
                    )
                except Exception:
                    pass  # Skip invalid tool calls

        # Create usage data object
        usage = UsageData(
            user_prompt=user_prompt,
            assistant_response=assistant_response,
            context=UsageContext(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=model,
                duration_ms=duration_ms,
            ),
            github_username=github_username,
            session_id=session_id,
            project_name=project_name,
            tool_calls=parsed_tool_calls,
        )

        # Send to Langfuse with additional metadata
        trace_id = usage_tracer.trace_usage(
            usage,
            repo_full_name=repo_full_name,
            repo_url=repo_url,
            message_count=message_count,
        )
        usage_tracer.flush()

        return {
            "status": "success",
            "trace_id": trace_id,
            "message": f"Usage reported for {github_username}",
            "tokens_used": usage.context.total_tokens,
        }

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[MCP Server] Error in report_usage: {e}", file=sys.stderr)
        print(f"[MCP Server] Traceback: {error_details}", file=sys.stderr)
        return {
            "status": "error",
            "message": f"{str(e)}",
            "trace_id": None,
            "error_type": type(e).__name__,
        }


@mcp.tool()
async def admin_generate_token(
    user_id: str, scopes: Optional[list[str]] = None
) -> dict:
    """
    [Admin Tool] Generate access token for a new team member.

    This tool creates a new authentication token that team members use to
    report their Claude Code usage. Tokens should be distributed securely.

    Args:
        user_id: GitHub username of the team member
        scopes: Permission scopes (defaults to ["usage:write"])

    Returns:
        dict: Token information including the generated token string
    """
    try:
        if scopes is None:
            scopes = ["usage:write"]

        token = token_verifier.generate_token(user_id, scopes)

        return {
            "status": "success",
            "token": token,
            "user_id": user_id,
            "scopes": scopes,
            "message": f"Token generated for {user_id}. Keep it secure!",
        }

    except Exception as e:
        return {"status": "error", "message": str(e), "token": None}


@mcp.tool()
async def admin_revoke_token(token: str) -> dict:
    """
    [Admin Tool] Revoke an access token.

    Use this to immediately revoke a team member's access token if needed
    (e.g., when they leave the team or token is compromised).

    Args:
        token: The token string to revoke

    Returns:
        dict: Revocation status
    """
    try:
        success = token_verifier.revoke_token(token)

        if success:
            return {
                "status": "success",
                "message": "Token revoked successfully",
                "revoked": True,
            }
        else:
            return {
                "status": "error",
                "message": "Token not found",
                "revoked": False,
            }

    except Exception as e:
        return {"status": "error", "message": str(e), "revoked": False}


@mcp.tool()
async def admin_list_tokens(include_revoked: bool = False) -> dict:
    """
    [Admin Tool] List all access tokens.

    Shows all tokens in the system with their status and metadata.

    Args:
        include_revoked: Whether to include revoked tokens in the list

    Returns:
        dict: List of tokens with their information
    """
    try:
        tokens = token_verifier.list_tokens(include_revoked=include_revoked)

        return {
            "status": "success",
            "count": len(tokens),
            "tokens": [
                {
                    "token_preview": f"{t['token'][:20]}...",
                    "user_id": t["user_id"],
                    "scopes": t["scopes"],
                    "revoked": t["revoked"],
                    "created_at": t["created_at"],
                }
                for t in tokens
            ],
        }

    except Exception as e:
        return {"status": "error", "message": str(e), "tokens": []}


@mcp.tool()
async def health_check() -> dict:
    """
    Check server health status.

    Returns:
        dict: Health status information
    """
    return {
        "status": "healthy",
        "server": "OSP Usage Monitor",
        "version": "0.1.0",
        "langfuse_configured": bool(
            config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY
        ),
    }


def main():
    """Run the MCP server"""
    # Validate configuration
    if not config.validate():
        print("Warning: Configuration validation failed. Check your .env file.")

    print(f"Starting MCP Server on {config.SERVER_URL}")
    print(f"Token registry: {config.TOKENS_FILE}")
    print(f"Langfuse host: {config.LANGFUSE_HOST}")

    # Run server with SSE transport (more stable than streamable-http)
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
