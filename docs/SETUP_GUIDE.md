# Hướng dẫn Setup

## Bước 1: Cấu hình Langfuse

### 1.1. Tạo tài khoản Langfuse

1. Truy cập https://cloud.langfuse.com (hoặc self-hosted instance của bạn)
2. Đăng ký tài khoản mới hoặc đăng nhập

### 1.2. Lấy API Keys

1. Vào **Settings** → **API Keys**
2. Click **Create New API Key**
3. Lưu lại:
   - **Public Key** (bắt đầu bằng `pk-lf-...`)
   - **Secret Key** (bắt đầu bằng `sk-lf-...`)

### 1.3. Cấu hình Environment Variables

Copy file `.env.example` sang `.env`:

```bash
cp .env.example .env
```

Chỉnh sửa `.env`:

```env
# MCP Server Configuration
TOKEN_SECRET_KEY=your-random-secret-key-here  # Generate với: openssl rand -hex 32
SERVER_URL=http://localhost:8000
AUTH_ISSUER_URL=https://auth.example.com

# Langfuse Configuration (QUAN TRỌNG!)
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key-here
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key-here
LANGFUSE_HOST=https://cloud.langfuse.com  # Hoặc URL self-hosted instance

# Client Configuration
MCP_USAGE_SERVER_URL=http://localhost:8000
MCP_USAGE_ACCESS_TOKEN=will-be-generated-later
```

## Bước 2: Cài đặt Dependencies

```bash
# Tạo virtual environment (khuyến nghị)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc: venv\Scripts\activate  # Windows

# Cài đặt dependencies
pip install -e .
```

## Bước 3: Generate Token Secret Key

```bash
# Generate một secret key ngẫu nhiên
openssl rand -hex 32

# Copy output và paste vào .env file (TOKEN_SECRET_KEY)
```

## Bước 4: Test MCP Server

### 4.1. Chạy server

```bash
python -m src.server
```

Bạn sẽ thấy output:

```
Starting MCP Server on http://localhost:8000
Token registry: tokens.json
Langfuse host: https://cloud.langfuse.com
```

### 4.2. Test health check

Mở terminal mới:

```bash
# Kiểm tra server health
curl http://localhost:8000/health
```

## Bước 5: Generate Access Token cho Team Members

### 5.1. Generate token cho chính bạn (test)

```bash
python scripts/admin_token.py generate your-github-username
```

Output sẽ là:

```
✅ Token generated successfully for: your-github-username

Token: your-github-username:1738483200:abc123def456

Scopes: usage:write

⚠️  Share this token securely with your-github-username. They should add it to their environment:

export MCP_USAGE_ACCESS_TOKEN="your-github-username:1738483200:abc123def456"
```

### 5.2. Set environment variable

```bash
# Thêm vào ~/.bashrc hoặc ~/.zshrc
echo 'export MCP_USAGE_ACCESS_TOKEN="your-token-here"' >> ~/.bashrc
source ~/.bashrc
```

## Bước 6: Cấu hình MCP CLI

### 6.1. Kiểm tra mcp-cli đã cài đặt

```bash
which mcp-cli
```

### 6.2. Thêm MCP Server vào config

Tạo hoặc chỉnh sửa `~/.config/mcp-cli/config.json`:

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

### 6.3. Test MCP tool

```bash
# Test health check tool
mcp-cli call usage-monitor/health_check '{}'
```

Nếu thành công, bạn sẽ thấy:

```json
{
  "status": "healthy",
  "server": "Claude Code Usage Monitor",
  "version": "0.1.0",
  "langfuse_configured": true
}
```

## Bước 7: Test Hook Manually

### 7.1. Tạo mock transcript file

```bash
cat > /tmp/test_transcript.json <<'EOF'
{
  "messages": [
    {
      "role": "user",
      "content": "Create a hello world function"
    },
    {
      "role": "assistant",
      "content": "Here is a hello world function: def hello(): print('Hello')"
    }
  ],
  "usage": {
    "input_tokens": 100,
    "output_tokens": 50
  },
  "model": "claude-sonnet-4-20250514",
  "session_id": "test-session-123",
  "start_time": 1000,
  "end_time": 3500
}
EOF
```

### 7.2. Test hook script

```bash
# Set environment
export TRANSCRIPT_PATH=/tmp/test_transcript.json
export MCP_USAGE_ACCESS_TOKEN="your-token-here"

# Run hook
python3 .claude/hooks/send_usage.py
```

Nếu thành công, bạn sẽ thấy:

```
[INFO] Reporting usage for your-github-username, project: mcp-ops-ai-use-monitor, tokens: 100+50
[INFO] ✅ Usage reported successfully
```

### 7.3. Kiểm tra trên Langfuse

1. Vào https://cloud.langfuse.com
2. Mở project của bạn
3. Vào **Traces**
4. Bạn sẽ thấy trace mới với:
   - Name: `claude-code-usage`
   - User ID: `your-github-username`
   - Tags: `claude-code`, `claude-sonnet-4-20250514`

## Bước 8: Enable Hook trong Claude Code

Hook đã được cấu hình sẵn trong `.claude/settings.json` của project này.

Để apply cho toàn bộ hệ thống, copy vào `~/.claude/settings.json`:

```bash
# Backup existing settings
cp ~/.claude/settings.json ~/.claude/settings.json.backup 2>/dev/null || true

# Merge hook config
cat > ~/.claude/settings.json <<'EOF'
{
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/send_usage.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
EOF

# Copy hook script
mkdir -p ~/.claude/hooks
cp .claude/hooks/send_usage.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/send_usage.py
```

## Bước 9: Test End-to-End với Claude Code

1. Mở một project bất kỳ với Claude Code
2. Gửi một prompt đơn giản: "Hello, test usage tracking"
3. Sau khi Claude trả lời xong, hook sẽ tự động chạy
4. Kiểm tra logs trong terminal
5. Kiểm tra trace mới trên Langfuse dashboard

## Troubleshooting

### Hook không chạy

```bash
# Check environment variables
echo $MCP_USAGE_ACCESS_TOKEN
echo $TRANSCRIPT_PATH

# Check hook script có executable không
ls -la ~/.claude/hooks/send_usage.py

# Test hook manually với transcript
TRANSCRIPT_PATH=/path/to/transcript.json python3 ~/.claude/hooks/send_usage.py
```

### MCP Server không kết nối

```bash
# Check server đang chạy
curl http://localhost:8000/health

# Check mcp-cli config
cat ~/.config/mcp-cli/config.json

# Test direct MCP call
mcp-cli call usage-monitor/health_check '{}'
```

### Langfuse không nhận data

```bash
# Verify credentials
python3 -c "from src.config import config; print(f'Public key: {config.LANGFUSE_PUBLIC_KEY[:20]}...')"

# Test Langfuse connection
python3 -c "from langfuse import Langfuse; lf = Langfuse(); print('Connected:', lf.auth_check())"
```

## Admin Commands

```bash
# Generate token cho user mới
python scripts/admin_token.py generate <github-username>

# List tất cả tokens
python scripts/admin_token.py list

# List kể cả revoked tokens
python scripts/admin_token.py list --include-revoked

# Revoke token
python scripts/admin_token.py revoke <token-string>

# Show config info
python scripts/admin_token.py info
```

## Deployment Production

### Docker

```bash
# Build và run
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop
docker-compose down
```

### Environment Variables cho Production

Đảm bảo set các biến môi trường:

```env
TOKEN_SECRET_KEY=<strong-random-key>
SERVER_URL=https://your-domain.com
LANGFUSE_PUBLIC_KEY=<your-key>
LANGFUSE_SECRET_KEY=<your-key>
```
