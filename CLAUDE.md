# CLAUDE.md - Project Guidelines

## Subagent Task Delegation

**Để tiết kiệm token và giữ context sạch, delegate các task sau cho subagent:**

### 1. Research/Explore Tasks → Use `Explore` subagent
Khi cần tìm hiểu codebase, search pattern, hoặc understand architecture:
```
Task: "Find where DNS rebinding protection is configured in FastMCP"
Task: "Search for all files that handle SSE transport"
Task: "Understand how middleware is added in Starlette apps"
```

### 2. Web Search/Fetch → Use `Explore` subagent với web tools
Khi cần tra cứu documentation hoặc GitHub issues:
```
Task: "Search GitHub issues for FastMCP 421 Invalid Host Header error and summarize the solution"
Task: "Find documentation for TransportSecuritySettings in MCP Python SDK"
```

### 3. Build/Test Validation → Use `Bash` subagent
Khi cần chạy build, test, hoặc verify changes:
```
Task: "Run docker-compose up -d --build and report if container starts successfully"
Task: "Test curl to http://10.10.10.63:8000/sse and report HTTP status"
```

### 4. Git Operations → Use `Bash` subagent
```
Task: "Create commit with message 'Fix DNS rebinding for external IP access'"
```

### Tasks Main Thread Should Handle
- **Code edits** - cần context từ conversation
- **Decision making** - cần user input
- **Final verification** - confirm với user
- **Multi-step refactoring** - cần maintain state

## Subagent Model Selection

Chọn model phù hợp để tối ưu cost và latency:

| Model | Use Case | Examples |
|-------|----------|----------|
| **haiku** | Simple, straightforward tasks | `docker ps`, `curl` test, `git status`, single file search |
| **sonnet** | Moderate complexity, multi-step | Build + test pipeline, multi-file grep, code review |
| **opus** | Complex research, architectural decisions | Codebase exploration, design decisions, debugging complex issues |

### Model Selection Rules

```
IF task is single command với output rõ ràng → haiku
IF task cần parse output và quyết định tiếp → sonnet
IF task cần reasoning sâu hoặc context lớn → opus (hoặc không specify để dùng default)
```

### Examples with Model

```python
# haiku - simple bash
Task(subagent_type="Bash", model="haiku",
     prompt="Run: docker-compose up -d --build")

# haiku - simple test
Task(subagent_type="Bash", model="haiku",
     prompt="Run: curl -s http://localhost:8000/health")

# sonnet - multi-step build + verify
Task(subagent_type="Bash", model="sonnet",
     prompt="Build docker image, start container, wait 5s, check logs for errors")

# sonnet - explore with specific goal
Task(subagent_type="Explore", model="sonnet",
     prompt="Find all API endpoints that accept POST requests")

# opus (default) - complex research
Task(subagent_type="Explore",
     prompt="Analyze authentication flow and identify security issues")
```

### Cost Optimization Tips

1. **Batch simple commands** cho 1 haiku task thay vì nhiều task riêng
2. **Prefer haiku** cho verification tasks (curl, docker ps, git status)
3. **Use sonnet** cho tasks cần parse và report kết quả
4. **Reserve opus** cho tasks cần deep reasoning

## Docker & External IP Access

**Problem**: FastMCP có DNS rebinding protection mặc định, block request từ IP khác localhost.

**Solution** (Reference: https://github.com/modelcontextprotocol/python-sdk/issues/1798):
```python
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

security_settings = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,  # Allow external IP
)

mcp = FastMCP(
    "server-name",
    transport_security=security_settings,  # NOT transport_security_settings
)
```

**Environment Variables cho Docker**:
```env
HOST=0.0.0.0
PORT=8000
```

## Langfuse v3 API Notes

**IMPORTANT**: Langfuse v3 SDK has different API compared to v2:

### Creating Traces
- **DO NOT** use `langfuse.trace()` - this method does not exist in v3
- **USE** `langfuse.start_as_current_span()` or `langfuse.start_span()` instead

### Token Usage
- **DO NOT** use `usage={}` parameter
- **USE** `usage_details={}` parameter instead

### Example (Correct v3 API):
```python
from langfuse._client.client import Langfuse

langfuse = Langfuse(
    public_key="...",
    secret_key="...",
    host="https://langfuse.example.com",
)

# Create trace with span
with langfuse.start_as_current_span(
    name="my-trace",
    input="user input",
    output="assistant output",
    metadata={"key": "value"},
):
    trace_id = langfuse.get_current_trace_id()

    # Update trace with user/session
    langfuse.update_current_trace(
        user_id="user123",
        session_id="session456",
        tags=["tag1", "tag2"],
    )

    # Create generation with token usage
    with langfuse.start_as_current_generation(
        name="generation",
        model="claude-opus-4.5",
        input="prompt",
        output="response",
    ):
        langfuse.update_current_generation(
            usage_details={
                "input": 1000,
                "output": 500,
                "total": 1500,
            }
        )

langfuse.flush()
```

### Import Note
In some Langfuse v3 installations, the main class may not be exported from `langfuse`:
```python
# May fail:
from langfuse import Langfuse

# Use instead:
try:
    from langfuse import Langfuse
except ImportError:
    from langfuse._client.client import Langfuse
```

## Project Structure

- `src/server_simple.py` - MCP Server với FastMCP (production, Docker)
- `src/server.py` - MCP Server với OAuth auth (development)
- `.claude/hooks/send_usage.py` - Stop hook parse transcript và gửi usage
- `.claude/settings.json` - Hook configuration

## Token Calculation Fix (Feb 2025)

**IMPORTANT**: Claude Code transcript's `input_tokens` field represents the **context window size** for that API call, NOT the user prompt token count.

- **OLD BEHAVIOR**: Summed all `input_tokens` from all messages → resulted in 17M+ tokens
- **NEW BEHAVIOR**: Take `input_tokens` from the **last assistant message only** → accurate per-prompt usage

The hook now correctly parses transcript by taking usage from the final message, not accumulating all messages.

## Metadata Enhancements (Feb 2025)

Added GitHub repository information to Langfuse traces:

- `repo_url`: Full git remote URL (e.g., `https://github.com/ospgroupvn/my-repo.git` or `git@github.com:ospgroupvn/my-repo.git`)
- `repo_full_name`: Owner/repo format (e.g., `ospgroupvn/my-repo`)
- `repo_name`: Just repository name (e.g., `my-repo`)
- `message_count`: Number of messages in the session

This information is extracted from `git remote get-url origin` and sent as metadata to Langfuse.

## Claude Code /context Command

The `/context` command in Claude Code shows token usage breakdown, but it's an internal command and **not directly accessible** to hooks.

Hook already gets context information from the **transcript file** via the `usage` field in each message, which contains the same information `/context` would display.

## Testing

Test hook locally:
```bash
echo '{"session_id": "test", "cwd": "/path/to/project"}' | python3 .claude/hooks/send_usage.py
```

Test MCP server (local):
```bash
source .venv/bin/activate
python -m src.server_simple
```

Test Docker container:
```bash
docker-compose up -d --build
curl -s http://localhost:8000/sse -H "X-MCP-API-Key: dev-api-key-123" --max-time 2
```

Test from external IP:
```bash
curl -s http://10.10.10.63:8000/sse -H "X-MCP-API-Key: dev-api-key-123" --max-time 2
```
