# CLAUDE.md - Project Guidelines

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

- `src/server.py` - MCP Server với FastMCP
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

Test MCP server:
```bash
source .venv/bin/activate
python -m src.server
```
