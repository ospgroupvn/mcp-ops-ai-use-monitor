# MCP Ops AI Use Monitor - Production

MCP Server để giám sát việc sử dụng Claude Code, tích hợp Langfuse.

## Production

| Item | Value |
|------|-------|
| MCP Server | `https://mcp-tracing.ospgroup.io.vn` |
| Langfuse | `https://langfuse.ospgroup.io.vn` |

## Setup cho Team Members

### 1. Cài dependencies

```bash
pip install mcp python-dotenv
# hoặc dùng uv:
uv pip install --system mcp python-dotenv
```

### 2. Copy `.claude` folder vào project

Copy toàn bộ thư mục `.claude` từ project này sang project khác.

### 3. Tạo `.env` file với API key

Trong project root, tạo file `.env`:

```bash
echo "MCP_API_KEY=<api-key>" > .env
```

Hook sẽ tự động tìm `.env` theo thứ tự:
- `<project>/.env` - Project directory (ưu tiên)
- `<project>/../.env` - Parent directory
- `~/mcp-ops-ai-use-monitor/.env` - Legacy path

### 4. Verify hook config

`.claude/settings.json` nên có:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/send_usage.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

## Test

```bash
# Test health
curl https://mcp-tracing.ospgroup.io.vn/health

# Test hook
echo '{"session_id":"test","cwd":"'"$PWD"'"}' | python3 .claude/hooks/send_usage.py
```

Expected output:
```
[usage-hook] Processing session: test
[usage-hook] Working directory: /path/to/project
[usage-hook] Found transcript: /home/user/.claude/projects/...
[usage-hook] Reported to MCP: trace_id=...
```

## Kiến trúc

```
Claude Code → Stop Hook → send_usage.py → MCP Server → Langfuse
```
