"""Simple MCP Server for Claude Code Usage Monitoring - HTTP/SSE Transport"""

import os
import warnings
from typing import Optional, List

warnings.filterwarnings("ignore", category=DeprecationWarning)

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel

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


# Pydantic models for HTTP API
class ToolCall(BaseModel):
    id: str = ""
    name: str = "unknown"
    input: dict = {}


class UsageReportRequest(BaseModel):
    user_prompt: str
    assistant_response: str
    github_username: str
    session_id: str
    model: str = "unknown"
    project_name: Optional[str] = None
    repo_full_name: Optional[str] = None
    repo_url: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    message_count: int = 0
    tool_calls: List[ToolCall] = []


async def _report_usage_internal(data: UsageReportRequest) -> dict:
    """Internal function to report usage to Langfuse."""
    try:
        print(f"[HTTP API] Reporting usage: user={data.github_username}, project={data.project_name}, model={data.model}")
        print(f"[HTTP API] Tokens: input={data.input_tokens}, output={data.output_tokens}, duration={data.duration_ms}ms")
        print(f"[HTTP API] Repo: {data.repo_full_name or 'N/A'}")
        print(f"[HTTP API] User prompt: {data.user_prompt[:100]}...")

        # Build metadata
        metadata = {
            "project_name": data.project_name or "unknown",
            "message_count": data.message_count,
            "source": "http-api",
        }
        if data.repo_url:
            metadata["repo_url"] = data.repo_url
        if data.repo_full_name:
            metadata["repo_full_name"] = data.repo_full_name

        # Add tool calls summary to metadata
        if data.tool_calls:
            tool_names = [tc.name for tc in data.tool_calls]
            metadata["tool_count"] = len(tool_names)
            metadata["tools_used"] = list(set(tool_names))[:20]  # Top 20 unique tools

        # Create trace using start_as_current_span (Langfuse v3 API)
        with langfuse.start_as_current_span(
            name="claude-code-session",
            input=data.user_prompt,
            output=data.assistant_response,
            metadata=metadata,
        ):
            trace_id = langfuse.get_current_trace_id()

            # Build tags
            tags = ["claude-code", data.model, data.project_name or "unknown"]
            if data.repo_full_name:
                tags.append(data.repo_full_name)

            # Update trace with user and session info
            langfuse.update_current_trace(
                user_id=data.github_username,
                session_id=data.session_id,
                tags=tags,
            )

            # Create generation with token usage
            with langfuse.start_as_current_generation(
                name="claude-code-generation",
                model=data.model,
                input=data.user_prompt,
                output=data.assistant_response,
                metadata={
                    "message_count": data.message_count,
                    "duration_ms": data.duration_ms,
                },
            ):
                langfuse.update_current_generation(
                    usage_details={
                        "input": data.input_tokens,
                        "output": data.output_tokens,
                        "total": data.input_tokens + data.output_tokens,
                    }
                )

        langfuse.flush()

        return {
            "status": "success",
            "trace_id": trace_id,
            "message": f"Usage reported for {data.github_username}",
            "tokens": {"input": data.input_tokens, "output": data.output_tokens},
        }

    except Exception as e:
        print(f"[HTTP API ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e), "trace_id": None}


def main():
    """Run the MCP server with SSE transport"""
    import uvicorn
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    print(f"Starting MCP Server on http://{host}:{port}")
    print(f"Langfuse host: {os.getenv('LANGFUSE_HOST', 'not configured')}")
    print(f"API Key authentication: {'enabled' if API_KEY else 'disabled'}")
    print("[SECURITY] DNS rebinding protection disabled (allows external IP access)")

    # Get the SSE app from FastMCP (security settings already configured at init)
    app = mcp.sse_app()

    # Add HTTP API endpoint for reporting usage
    async def http_report_usage(request: Request):
        """HTTP POST endpoint for reporting usage - alternative to MCP tool."""
        # Check API key
        api_key = request.headers.get("X-MCP-API-Key")
        if API_KEY and (not api_key or api_key != API_KEY):
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing API key"},
            )

        try:
            body = await request.json()
            data = UsageReportRequest(**body)
            result = await _report_usage_internal(data)
            status_code = 200 if result.get("status") == "success" else 500
            return JSONResponse(status_code=status_code, content=result)
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": str(e)},
            )

    async def http_health_check(request: Request):
        """HTTP GET endpoint for health check."""
        return JSONResponse(content={
            "status": "healthy",
            "server": "OSP Usage Monitor",
            "version": "0.1.0",
            "langfuse_host": os.getenv("LANGFUSE_HOST", "not configured"),
        })

    # Add routes to app
    app.routes.append(Route("/api/report-usage", http_report_usage, methods=["POST"]))
    app.routes.append(Route("/api/health", http_health_check, methods=["GET"]))
    app.routes.append(Route("/health", http_health_check, methods=["GET"]))

    print("[HTTP API] Added endpoints: POST /api/report-usage, GET /api/health, GET /health")

    # Add API Key middleware if configured
    if API_KEY:
        class APIKeyMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                # Skip auth for health check endpoints
                if request.url.path in ["/health", "/api/health"]:
                    return await call_next(request)

                # Skip auth for HTTP API endpoints (they handle auth internally)
                if request.url.path == "/api/report-usage":
                    return await call_next(request)

                # Check for API key in header for MCP/SSE endpoints
                api_key = request.headers.get("X-MCP-API-Key")

                if not api_key or api_key != API_KEY:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid or missing API key"},
                    )

                # API key valid, proceed with request
                response = await call_next(request)
                return response

        # Add middleware to the app
        app.add_middleware(APIKeyMiddleware)
        print(f"[AUTH] API Key middleware enabled - header: X-MCP-API-Key")

    # Run with uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
