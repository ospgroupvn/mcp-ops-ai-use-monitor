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
```

### 2. Tạo file cấu hình

```bash
mkdir -p ~/.claude/hooks ~/mcp-ops-ai-use-monitor
```

### 3. Tạo .env với API key

```bash
echo "MCP_API_KEY=<api-key>" > ~/mcp-ops-ai-use-monitor/.env
```

### 4. Copy hook script

```bash
cp .claude/hooks/send_usage.py ~/.claude/hooks/
```

### 5. Thêm Stop hook vào `~/.claude/settings.local.json`

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/send_usage.py",
            "timeout": 30000
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
echo '{"session_id":"test","cwd":"'$PWD'"}' | python3 ~/.claude/hooks/send_usage.py
```

## Kiến trúc

```
Claude Code → Stop Hook → send_usage.py → MCP Server → Langfuse
```
