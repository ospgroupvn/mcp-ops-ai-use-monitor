"""Simple MCP Server for Claude Code Usage Monitoring - HTTP/SSE Transport"""

import os
import warnings
from typing import Optional

warnings.filterwarnings("ignore", category=DeprecationWarning)

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

load_dotenv()

# API Key for authentication
API_KEY = os.getenv("MCP_API_KEY", "")

# Initialize Langfuse - use internal import path for v3 compatibility
try:
    from langfuse import Langfuse
except ImportError:
    from langfuse._client.client import Langfuse

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)

# Configure transport security to allow external access
# Reference: https://github.com/modelcontextprotocol/python-sdk/issues/1798
# Option 2: Disable DNS Rebinding Protection for local network access
security_settings = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,  # Disable for local network access
)

# Initialize MCP Server with security settings
mcp = FastMCP(
    "osp-usage-monitor",
    transport_security=security_settings,
)


@mcp.tool()
async def report_usage(
    user_prompt: str,
    assistant_response: str,
    github_username: str,
    session_id: str,
    model: str = "unknown",
    project_name: Optional[str] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    message_count: int = 0,
) -> dict:
    """
    Report Claude Code usage data and send to Langfuse.

    Args:
        user_prompt: The user's prompt content (truncated)
        assistant_response: Claude's response content (truncated)
        github_username: GitHub username from git config
        session_id: Claude Code session ID
        model: Model identifier
        project_name: Project name
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens generated
        message_count: Number of messages in session

    Returns:
        dict: Status and trace information
    """
    try:
        print(f"[MCP] Reporting usage: user={github_username}, project={project_name}, model={model}")
        print(f"[MCP] Tokens: input={input_tokens}, output={output_tokens}")
        print(f"[MCP] User prompt: {user_prompt[:100]}...")

        # Create trace using start_as_current_span (Langfuse v3 API)
        with langfuse.start_as_current_span(
            name="claude-code-session",
            input=user_prompt,
            output=assistant_response,
            metadata={
                "project_name": project_name or "unknown",
                "message_count": message_count,
                "source": "mcp-hook",
            },
        ):
            trace_id = langfuse.get_current_trace_id()

            # Update trace with user and session info
            langfuse.update_current_trace(
                user_id=github_username,
                session_id=session_id,
                tags=["claude-code", model, project_name or "unknown"],
            )

            # Create generation with token usage
            with langfuse.start_as_current_generation(
                name="claude-code-generation",
                model=model,
                input=user_prompt,
                output=assistant_response,
                metadata={
                    "message_count": message_count,
                },
            ):
                langfuse.update_current_generation(
                    usage_details={
                        "input": input_tokens,
                        "output": output_tokens,
                        "total": input_tokens + output_tokens,
                    }
                )

        langfuse.flush()

        return {
            "status": "success",
            "trace_id": trace_id,
            "message": f"Usage reported for {github_username}",
            "tokens": {"input": input_tokens, "output": output_tokens},
        }

    except Exception as e:
        print(f"[MCP ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e), "trace_id": None}


@mcp.tool()
async def health_check() -> dict:
    """Check server health status."""
    return {
        "status": "healthy",
        "server": "OSP Usage Monitor",
        "version": "0.1.0",
        "langfuse_host": os.getenv("LANGFUSE_HOST", "not configured"),
    }


def main():
    """Run the MCP server with SSE transport"""
    import uvicorn
    from starlette.responses import JSONResponse

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    print(f"Starting MCP Server on http://{host}:{port}")
    print(f"Langfuse host: {os.getenv('LANGFUSE_HOST', 'not configured')}")
    print(f"API Key authentication: {'enabled' if API_KEY else 'disabled'}")
    print("[SECURITY] DNS rebinding protection disabled (allows external IP access)")

    # Get the SSE app from FastMCP
    sse_app = mcp.sse_app()

    # Create wrapper app with API key check (ASGI-native, SSE compatible)
    async def app(scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")

            # Health endpoint - no auth required
            if path == "/health":
                response = JSONResponse(
                    status_code=200,
                    content={"status": "healthy", "version": "0.1.0"},
                )
                await response(scope, receive, send)
                return

            # Check API key for other endpoints
            if API_KEY:
                headers = dict(scope.get("headers", []))
                api_key = headers.get(b"x-mcp-api-key", b"").decode()

                if api_key != API_KEY:
                    response = JSONResponse(
                        status_code=401,
                        content={"error": "Invalid or missing API key"},
                    )
                    await response(scope, receive, send)
                    return

        # Fix host header for MCP SSE validation when behind reverse proxy
        # MCP library validates host header - override to localhost
        if scope["type"] == "http":
            new_headers = []
            for name, value in scope.get("headers", []):
                if name == b"host":
                    new_headers.append((b"host", b"localhost:8000"))
                else:
                    new_headers.append((name, value))
            scope = dict(scope)
            scope["headers"] = new_headers

        # Pass through to SSE app
        await sse_app(scope, receive, send)

    if API_KEY:
        print(f"[AUTH] API Key middleware enabled - header: X-MCP-API-Key")

    # Run with uvicorn (proxy headers enabled for K8s/reverse proxy)
    uvicorn.run(
        app,
        host=host,
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
