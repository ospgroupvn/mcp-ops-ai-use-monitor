# MCP Ops AI Use Monitor

MCP Server để giám sát việc sử dụng Claude Code của team members, với tích hợp Langfuse để tracing và observability.

## Tính năng

- 🔐 API Key authentication để bảo vệ server
- 📊 Tự động tracking usage sau mỗi prompt
- 📈 Integration với Langfuse để analytics
- 🎯 Track tokens, model, duration, user info
- 🐳 Docker support để dễ deploy

## Kiến trúc

```
Claude Code CLI → Stop Hook → MCP Server (FastMCP) → Langfuse
```

## Cài đặt

### 1. Setup Server với Docker

```bash
# Clone repository
git clone <repo-url>
cd mcp-ops-ai-use-monitor

# Configure environment
cp .env.example .env
# Edit .env với Langfuse credentials và API key
```

File `.env` của bạn cần có:

```env
# MCP API Key (bắt buộc - thay đổi ở production)
MCP_API_KEY=your-secure-api-key-here

# Langfuse Configuration
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 2. Chạy Server

```bash
# Production với Docker
docker-compose up -d
```

Server sẽ chạy tại `http://localhost:8000`

### 3. Configure Claude Code Hook (Team Members)

Thiết lập biến môi trường với API key:

```bash
# Thêm vào ~/.bashrc hoặc ~/.zshrc
export MCP_USAGE_API_KEY="your-secure-api-key-here"
export MCP_USAGE_SERVER_URL="https://your-server.com"
```

### 4. Configure Claude Code Settings

Thêm vào `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "usage-monitor": {
      "url": "https://your-server.com/sse",
      "headers": {
        "X-MCP-API-Key": "your-secure-api-key-here"
      }
    }
  },
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

## Authentication

Server sử dụng **API Key authentication** thông qua header `X-MCP-API-Key`. Bạn cần:

1. Đặt `MCP_API_KEY` trong file `.env` khi start server
2. Gửi header `X-MCP-API-Key` khi configure MCP client trong Claude Code settings

### Cấu hình MCP Client

Trong `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "usage-monitor": {
      "url": "https://your-server.com/sse",
      "headers": {
        "X-MCP-API-Key": "${env:MCP_USAGE_API_KEY}"
      }
    }
  }
}
```

## Usage

Sau khi cài đặt, hook sẽ tự động gửi usage data sau mỗi prompt trong Claude Code. Data có thể xem trên Langfuse dashboard.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint code
ruff check src/
```

## Documentation

Xem thêm trong thư mục [docs/](docs/):

- [docs/QUICKSTART.md](docs/QUICKSTART.md) - Hướng dẫn nhanh
- [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) - Hướng dẫn chi tiết
- [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) - Chi tiết kiến trúc
- [docs/IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md) - Tóm tắt implementation

## License

MIT
