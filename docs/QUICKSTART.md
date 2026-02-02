# Quick Start Guide

## ✅ Langfuse đã được cấu hình thành công!

Trace ID test: `59edf7a5575f284d797a33dc2c9f9470`

View tại: https://langfuse.ospgroup.io.vn

---

## 🚀 Các bước tiếp theo

### 1. Generate Token cho bản thân

```bash
python scripts/admin_token.py generate $(git config --global user.name)
```

Copy token và set environment variable:

```bash
export MCP_USAGE_ACCESS_TOKEN="your-token-here"
```

### 2. Chạy MCP Server

```bash
python -m src.server
```

Server sẽ chạy tại `http://localhost:8000`

### 3. Cấu hình MCP CLI

Tạo file `~/.config/claude-code/mcp-servers.json`:

```json
{
  "mcpServers": {
    "usage-monitor": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/Users/namnguyenhoai/code/projects/2026/mcp-ops-ai-use-monitor",
      "env": {
        "MCP_USAGE_ACCESS_TOKEN": "your-token-here"
      }
    }
  }
}
```

Hoặc nếu server đang chạy riêng, tạo file `~/.config/mcp-cli/config.json`:

```json
{
  "servers": {
    "usage-monitor": {
      "url": "http://localhost:8000/mcp",
      "transport": "http",
      "headers": {
        "Authorization": "Bearer ${MCP_USAGE_ACCESS_TOKEN}"
      }
    }
  }
}
```

### 4. Test MCP Tools

```bash
# Test health check
mcp-cli call usage-monitor/health_check '{}'

# Test report usage (manually)
mcp-cli call usage-monitor/report_usage - <<'EOF'
{
  "user_prompt": "Test prompt",
  "assistant_response": "Test response",
  "input_tokens": 100,
  "output_tokens": 50,
  "model": "claude-sonnet-4-20250514",
  "duration_ms": 2000,
  "github_username": "test-user",
  "session_id": "test-session",
  "project_name": "test-project"
}
EOF
```

### 5. Enable Hook trong Claude Code

Hook đã được configured trong `.claude/settings.json`.

Để test hook:

```bash
# Set environment
export TRANSCRIPT_PATH=/tmp/test_transcript.json
export MCP_USAGE_ACCESS_TOKEN="your-token"

# Create test transcript
cat > /tmp/test_transcript.json <<'EOF'
{
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
  ],
  "usage": {"input_tokens": 10, "output_tokens": 5},
  "model": "claude-sonnet-4-20250514",
  "session_id": "test-123",
  "start_time": 1000,
  "end_time": 3000
}
EOF

# Run hook
python3 .claude/hooks/send_usage.py
```

### 6. View Data trong Langfuse

1. Truy cập: https://langfuse.ospgroup.io.vn
2. Vào **Traces**
3. Filter:
   - By user: Click vào user ID
   - By model: Check tags `claude-code`, model name
   - By project: Check metadata `project_name`

---

## 🔧 Admin Commands

```bash
# Generate token
python scripts/admin_token.py generate <username>

# List tokens
python scripts/admin_token.py list

# Revoke token
python scripts/admin_token.py revoke <token>

# Show config
python scripts/admin_token.py info
```

---

## 📊 Dashboard Metrics

Trong Langfuse dashboard, bạn có thể xem:

1. **Total Usage**: Tổng số prompts, tokens used
2. **Cost Analysis**: Chi phí theo user/project/model
3. **Performance**: Latency trung bình (duration_ms)
4. **Active Users**: Users đang active
5. **Model Distribution**: Phân bố sử dụng models

---

## 🐛 Troubleshooting

### MCP Server không start

```bash
# Check dependencies
pip install -e .

# Check .env file
cat .env

# Test Langfuse connection
python scripts/test_langfuse_v2.py
```

### Hook không gửi data

```bash
# Check environment
echo $MCP_USAGE_ACCESS_TOKEN

# Test hook manually
export TRANSCRIPT_PATH=/tmp/test_transcript.json
python3 .claude/hooks/send_usage.py
```

### Langfuse không nhận data

```bash
# Test tracer directly
python scripts/test_usage_tracer.py

# Check Langfuse credentials
python -c "from src.config import config; print(config.LANGFUSE_HOST)"
```
