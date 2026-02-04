# MCP Ops AI Use Monitor - Production

Service giám sát việc sử dụng Claude Code, tích hợp Langfuse để track usage, tokens và chi phí.

## Production URLs

| Service | URL |
|---------|-----|
| API Server | `https://mcp-tracing.ospgroup.io.vn` |
| Langfuse Dashboard | `https://langfuse.ospgroup.io.vn` |

## Setup cho Team Members

### Bước 1: Cài dependency (chỉ cần python-dotenv)

```bash
pip install python-dotenv

# Hoặc dùng uv:
uv pip install --system python-dotenv
```

### Bước 2: Copy hook files vào project

**Copy 3 files sau vào project của bạn:**

```bash
# Trong project đang dùng Claude Code
mkdir -p .claude/hooks

# Copy 2 hook files
cp /path/to/mcp-ops-ai-use-monitor/.claude/hooks/send_usage.sh .claude/hooks/
cp /path/to/mcp-ops-ai-use-monitor/.claude/hooks/send_usage.py .claude/hooks/

# Make executable
chmod +x .claude/hooks/send_usage.sh
chmod +x .claude/hooks/send_usage.py
```

### Bước 3: Tạo .env file

Tạo file `.env` **trong project root** (cùng cấp với `.claude/`):

```bash
cat > .env << 'EOF'
MCP_API_KEY=<api-key>
MCP_USAGE_SERVER_URL=https://mcp-tracing.ospgroup.io.vn/sse
EOF
```

### Bước 4: Tạo settings.json

Tạo hoặc update file `.claude/settings.json`:

```bash
cat > .claude/settings.json << 'EOF'
{
  "env": {
    "MCP_API_KEY": "${MCP_API_KEY}",
    "MCP_USAGE_SERVER_URL": "${MCP_USAGE_SERVER_URL}"
  },
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/send_usage.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
EOF
```

### Bước 5: Test

**Test hook manually:**
```bash
cd /your/project

# Test với session ID fake
echo '{"session_id":"test-001","cwd":"'$(pwd)'"}' | python3 .claude/hooks/send_usage.py
```

**Expected output:**
```
[usage-hook] Processing session: test-001
[usage-hook] Working directory: /your/project
[usage-hook] Found transcript: /home/user/.claude/projects/...
[usage-hook] User: your.email@example.com, Repo: owner/repo, Model: claude-sonnet-4.5, Tokens: 100+50, Duration: 5000ms, Tools: 5 tools
[usage-hook] Reported to API: trace_id=abc123...
```


