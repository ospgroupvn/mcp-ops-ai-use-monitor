# Implementation Plan: MCP Server cho Claude Code Usage Monitoring

## Tổng quan

Xây dựng một hệ thống giám sát việc sử dụng Claude Code của các thành viên trong dự án, bao gồm:
1. **MCP Server** (Python) - Nhận và xử lý dữ liệu sử dụng
2. **Claude Code Hook** - Gửi dữ liệu sau mỗi prompt
3. **Langfuse Integration** - Tracing và observability

---

## Kiến trúc hệ thống

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│   Claude Code CLI   │────▶│    MCP Server       │────▶│    Langfuse     │
│   (với Stop Hook)   │     │    (Python/FastMCP) │     │    (Tracing)    │
└─────────────────────┘     └─────────────────────┘     └─────────────────┘
         │                           │
         │                           │
    ┌────▼────┐                ┌─────▼─────┐
    │ GitHub  │                │  Token    │
    │ Username│                │  Manager  │
    └─────────┘                └───────────┘
```

---

## Phần 1: MCP Server (Python)

### 1.1 Cấu trúc thư mục

```
mcp-ops-ai-use-monitor/
├── src/
│   ├── __init__.py
│   ├── server.py              # FastMCP server chính
│   ├── auth/
│   │   ├── __init__.py
│   │   └── token_verifier.py  # Xác thực access token
│   ├── langfuse/
│   │   ├── __init__.py
│   │   └── tracer.py          # Langfuse integration
│   ├── models/
│   │   ├── __init__.py
│   │   └── usage_data.py      # Pydantic models
│   └── config.py              # Configuration
├── tests/
│   ├── __init__.py
│   ├── test_server.py
│   ├── test_auth.py
│   └── test_langfuse.py
├── hooks/
│   └── send_usage.sh          # Claude Code hook script
├── .env.example
├── pyproject.toml
├── README.md
└── docker-compose.yml         # Optional: cho deployment
```

### 1.2 Dependencies (pyproject.toml)

```toml
[project]
name = "mcp-ops-ai-use-monitor"
version = "0.1.0"
description = "MCP Server for monitoring Claude Code usage"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.9.0",
    "langfuse>=3.0.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.5.0",
]
```

### 1.3 Data Models (models/usage_data.py)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class UsageContext(BaseModel):
    """Context của một prompt usage"""
    input_tokens: int = Field(..., description="Số token input")
    output_tokens: int = Field(..., description="Số token output")
    model: str = Field(..., description="Model đã sử dụng (e.g., claude-sonnet-4-20250514)")
    duration_ms: int = Field(..., description="Thời gian xử lý (ms)")

class UsageData(BaseModel):
    """Dữ liệu sử dụng Claude Code"""
    user_prompt: str = Field(..., description="Nội dung prompt của user")
    assistant_response: str = Field(..., description="Response từ Claude")
    context: UsageContext = Field(..., description="Thông tin context")
    github_username: str = Field(..., description="GitHub username của người dùng")
    session_id: str = Field(..., description="Session ID của Claude Code")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    project_name: Optional[str] = Field(None, description="Tên project đang làm việc")
```

### 1.4 Token Verifier (auth/token_verifier.py)

```python
from mcp.server.auth.provider import AccessToken, TokenVerifier
from typing import Optional
import hashlib
import hmac
from datetime import datetime

class AdminTokenVerifier(TokenVerifier):
    """
    Xác thực access token do admin phát hành.
    Token format: {user_id}:{timestamp}:{signature}
    """

    def __init__(self, secret_key: str, valid_tokens: dict[str, dict]):
        """
        Args:
            secret_key: Secret key để verify signature
            valid_tokens: Dict mapping token -> user info
                         Có thể load từ database hoặc file
        """
        self.secret_key = secret_key
        self.valid_tokens = valid_tokens  # Token registry

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """Verify và trả về AccessToken nếu hợp lệ"""

        # Kiểm tra token có trong registry không
        if token not in self.valid_tokens:
            return None

        token_info = self.valid_tokens[token]

        # Kiểm tra token có bị revoke không
        if token_info.get("revoked", False):
            return None

        # Kiểm tra expiration
        expires_at = token_info.get("expires_at")
        if expires_at and datetime.utcnow() > expires_at:
            return None

        return AccessToken(
            token=token,
            scopes=token_info.get("scopes", ["usage:write"]),
            expires_at=expires_at,
            client_id=token_info.get("user_id")
        )

    def generate_token(self, user_id: str, scopes: list[str] = None) -> str:
        """Generate new access token cho user"""
        timestamp = int(datetime.utcnow().timestamp())
        payload = f"{user_id}:{timestamp}"
        signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        return f"{payload}:{signature}"

    def revoke_token(self, token: str) -> bool:
        """Thu hồi token"""
        if token in self.valid_tokens:
            self.valid_tokens[token]["revoked"] = True
            return True
        return False
```

### 1.5 Langfuse Tracer (langfuse/tracer.py)

```python
from langfuse import Langfuse, get_client
from ..models.usage_data import UsageData
import os

class UsageTracer:
    """Gửi usage data lên Langfuse"""

    def __init__(self):
        self.langfuse = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        )

    def trace_usage(self, usage: UsageData) -> str:
        """
        Tạo trace trên Langfuse cho một usage event

        Returns:
            trace_id: ID của trace đã tạo
        """
        # Tạo trace chính
        trace = self.langfuse.trace(
            name="claude-code-usage",
            user_id=usage.github_username,
            session_id=usage.session_id,
            input={"user_prompt": usage.user_prompt},
            output={"assistant_response": usage.assistant_response},
            metadata={
                "project_name": usage.project_name,
                "timestamp": usage.timestamp.isoformat(),
            },
            tags=["claude-code", usage.context.model]
        )

        # Tạo generation span cho LLM call
        generation = trace.generation(
            name="claude-code-generation",
            model=usage.context.model,
            input=usage.user_prompt,
            output=usage.assistant_response,
            usage={
                "input": usage.context.input_tokens,
                "output": usage.context.output_tokens,
                "total": usage.context.input_tokens + usage.context.output_tokens
            },
            metadata={
                "duration_ms": usage.context.duration_ms,
            }
        )
        generation.end()

        return trace.id

    def flush(self):
        """Đảm bảo tất cả data được gửi"""
        self.langfuse.flush()

    def shutdown(self):
        """Shutdown client"""
        self.langfuse.shutdown()
```

### 1.6 MCP Server chính (server.py)

```python
from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl
import os
from dotenv import load_dotenv

from .auth.token_verifier import AdminTokenVerifier
from .langfuse.tracer import UsageTracer
from .models.usage_data import UsageData, UsageContext

load_dotenv()

# Load token registry (trong production nên load từ database)
TOKEN_REGISTRY = {
    # Format: token -> user info
    # Sẽ được populate từ database hoặc config
}

# Khởi tạo components
token_verifier = AdminTokenVerifier(
    secret_key=os.getenv("TOKEN_SECRET_KEY", "change-me-in-production"),
    valid_tokens=TOKEN_REGISTRY
)

usage_tracer = UsageTracer()

# Khởi tạo MCP Server với authentication
mcp = FastMCP(
    "Claude Code Usage Monitor",
    json_response=True,
    token_verifier=token_verifier,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(os.getenv("AUTH_ISSUER_URL", "https://auth.example.com")),
        resource_server_url=AnyHttpUrl(os.getenv("SERVER_URL", "http://localhost:8000")),
        required_scopes=["usage:write"]
    )
)


@mcp.tool()
async def report_usage(
    user_prompt: str,
    assistant_response: str,
    input_tokens: int,
    output_tokens: int,
    model: str,
    duration_ms: int,
    github_username: str,
    session_id: str,
    project_name: str = None
) -> dict:
    """
    Báo cáo usage data từ Claude Code.

    Args:
        user_prompt: Nội dung prompt của user
        assistant_response: Response từ Claude
        input_tokens: Số token input
        output_tokens: Số token output
        model: Model đã sử dụng
        duration_ms: Thời gian xử lý (ms)
        github_username: GitHub username
        session_id: Session ID
        project_name: Tên project (optional)

    Returns:
        dict với trace_id và status
    """
    usage = UsageData(
        user_prompt=user_prompt,
        assistant_response=assistant_response,
        context=UsageContext(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            duration_ms=duration_ms
        ),
        github_username=github_username,
        session_id=session_id,
        project_name=project_name
    )

    try:
        trace_id = usage_tracer.trace_usage(usage)
        usage_tracer.flush()

        return {
            "status": "success",
            "trace_id": trace_id,
            "message": f"Usage reported for {github_username}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@mcp.tool()
async def admin_generate_token(
    user_id: str,
    scopes: list[str] = None
) -> dict:
    """
    [Admin only] Generate access token cho user mới.

    Args:
        user_id: GitHub username của user
        scopes: List các scopes cho token

    Returns:
        dict với token mới
    """
    if scopes is None:
        scopes = ["usage:write"]

    token = token_verifier.generate_token(user_id, scopes)

    # Lưu vào registry
    TOKEN_REGISTRY[token] = {
        "user_id": user_id,
        "scopes": scopes,
        "revoked": False,
        "expires_at": None  # Hoặc set expiration
    }

    return {
        "status": "success",
        "token": token,
        "user_id": user_id,
        "scopes": scopes
    }


@mcp.tool()
async def admin_revoke_token(token: str) -> dict:
    """
    [Admin only] Thu hồi access token.

    Args:
        token: Token cần thu hồi

    Returns:
        dict với status
    """
    success = token_verifier.revoke_token(token)

    return {
        "status": "success" if success else "error",
        "message": "Token revoked" if success else "Token not found"
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

---

## Phần 2: Claude Code Hook

### 2.1 Hook Configuration (~/.claude/settings.json hoặc project .claude/settings.json)

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/send_usage.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### 2.2 Hook Script (hooks/send_usage.sh)

```bash
#!/bin/bash
# Claude Code Usage Reporter Hook
# Gửi usage data lên MCP Server sau mỗi prompt

set -e

# Configuration
MCP_SERVER_URL="${MCP_USAGE_SERVER_URL:-http://localhost:8000}"
ACCESS_TOKEN="${MCP_USAGE_ACCESS_TOKEN}"

# Lấy GitHub username từ git config
GITHUB_USERNAME=$(git config --global user.name 2>/dev/null || echo "unknown")

# Lấy project name từ thư mục hiện tại
PROJECT_NAME=$(basename "$(pwd)")

# Đọc transcript nếu có
TRANSCRIPT_PATH="${TRANSCRIPT_PATH:-}"

if [ -z "$ACCESS_TOKEN" ]; then
    echo "Warning: MCP_USAGE_ACCESS_TOKEN not set, skipping usage report" >&2
    exit 0
fi

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
    echo "Warning: TRANSCRIPT_PATH not available, skipping usage report" >&2
    exit 0
fi

# Parse transcript để lấy thông tin
# Transcript là JSON file chứa conversation history
LAST_USER_PROMPT=$(jq -r '.messages | map(select(.role == "user")) | last | .content' "$TRANSCRIPT_PATH" 2>/dev/null || echo "")
LAST_ASSISTANT_RESPONSE=$(jq -r '.messages | map(select(.role == "assistant")) | last | .content' "$TRANSCRIPT_PATH" 2>/dev/null || echo "")

# Lấy usage info từ transcript metadata
INPUT_TOKENS=$(jq -r '.usage.input_tokens // 0' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
OUTPUT_TOKENS=$(jq -r '.usage.output_tokens // 0' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
MODEL=$(jq -r '.model // "unknown"' "$TRANSCRIPT_PATH" 2>/dev/null || echo "unknown")
SESSION_ID=$(jq -r '.session_id // "unknown"' "$TRANSCRIPT_PATH" 2>/dev/null || echo "unknown")

# Tính duration (nếu có start_time và end_time)
START_TIME=$(jq -r '.start_time // 0' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
END_TIME=$(jq -r '.end_time // 0' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
DURATION_MS=$((END_TIME - START_TIME))

# Gửi data lên MCP Server qua mcp-cli
mcp-cli call usage-monitor/report_usage - <<EOF
{
  "user_prompt": $(echo "$LAST_USER_PROMPT" | jq -Rs .),
  "assistant_response": $(echo "$LAST_ASSISTANT_RESPONSE" | jq -Rs .),
  "input_tokens": $INPUT_TOKENS,
  "output_tokens": $OUTPUT_TOKENS,
  "model": "$MODEL",
  "duration_ms": $DURATION_MS,
  "github_username": "$GITHUB_USERNAME",
  "session_id": "$SESSION_ID",
  "project_name": "$PROJECT_NAME"
}
EOF

echo "Usage reported successfully" >&2
```

### 2.3 Alternative: Python Hook Script (hooks/send_usage.py)

```python
#!/usr/bin/env python3
"""
Claude Code Usage Reporter Hook
Gửi usage data lên MCP Server sau mỗi prompt
"""

import json
import os
import subprocess
import sys
from pathlib import Path

def get_github_username() -> str:
    """Lấy GitHub username từ git config"""
    try:
        result = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True,
            text=True
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"

def get_project_name() -> str:
    """Lấy project name từ thư mục hiện tại"""
    return Path.cwd().name

def parse_transcript(transcript_path: str) -> dict:
    """Parse transcript file để lấy thông tin usage"""
    try:
        with open(transcript_path, 'r') as f:
            transcript = json.load(f)

        messages = transcript.get('messages', [])
        user_messages = [m for m in messages if m.get('role') == 'user']
        assistant_messages = [m for m in messages if m.get('role') == 'assistant']

        return {
            'user_prompt': user_messages[-1].get('content', '') if user_messages else '',
            'assistant_response': assistant_messages[-1].get('content', '') if assistant_messages else '',
            'input_tokens': transcript.get('usage', {}).get('input_tokens', 0),
            'output_tokens': transcript.get('usage', {}).get('output_tokens', 0),
            'model': transcript.get('model', 'unknown'),
            'session_id': transcript.get('session_id', 'unknown'),
            'duration_ms': transcript.get('end_time', 0) - transcript.get('start_time', 0)
        }
    except Exception as e:
        print(f"Error parsing transcript: {e}", file=sys.stderr)
        return None

def send_usage(data: dict):
    """Gửi usage data lên MCP Server"""
    access_token = os.environ.get('MCP_USAGE_ACCESS_TOKEN')

    if not access_token:
        print("Warning: MCP_USAGE_ACCESS_TOKEN not set", file=sys.stderr)
        return

    # Thêm thông tin user
    data['github_username'] = get_github_username()
    data['project_name'] = get_project_name()

    # Gửi qua mcp-cli
    json_data = json.dumps(data)

    try:
        result = subprocess.run(
            ['mcp-cli', 'call', 'usage-monitor/report_usage', '-'],
            input=json_data,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("Usage reported successfully", file=sys.stderr)
        else:
            print(f"Error reporting usage: {result.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"Error calling mcp-cli: {e}", file=sys.stderr)

def main():
    transcript_path = os.environ.get('TRANSCRIPT_PATH')

    if not transcript_path or not Path(transcript_path).exists():
        print("Warning: TRANSCRIPT_PATH not available", file=sys.stderr)
        return

    data = parse_transcript(transcript_path)

    if data:
        send_usage(data)

if __name__ == '__main__':
    main()
```

---

## Phần 3: Configuration & Deployment

### 3.1 Environment Variables (.env.example)

```env
# MCP Server
TOKEN_SECRET_KEY=your-secret-key-change-in-production
SERVER_URL=http://localhost:8000
AUTH_ISSUER_URL=https://auth.example.com

# Langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com

# Client-side (cho hooks)
MCP_USAGE_SERVER_URL=http://localhost:8000
MCP_USAGE_ACCESS_TOKEN=your-access-token
```

### 3.2 Docker Deployment (docker-compose.yml)

```yaml
version: '3.8'

services:
  mcp-usage-monitor:
    build: .
    ports:
      - "8000:8000"
    environment:
      - TOKEN_SECRET_KEY=${TOKEN_SECRET_KEY}
      - SERVER_URL=${SERVER_URL}
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
      - LANGFUSE_HOST=${LANGFUSE_HOST}
    volumes:
      - ./tokens.json:/app/tokens.json:ro  # Token registry
    restart: unless-stopped
```

### 3.3 Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ ./src/

# Run server
CMD ["python", "-m", "src.server"]
```

---

## Phần 4: Admin Token Management

### 4.1 Token Registry Storage (tokens.json)

```json
{
  "tokens": {
    "user1:1234567890:abc123def456": {
      "user_id": "user1",
      "scopes": ["usage:write"],
      "revoked": false,
      "created_at": "2026-02-02T10:00:00Z",
      "expires_at": null
    }
  }
}
```

### 4.2 Admin CLI Script (scripts/admin_token.py)

```python
#!/usr/bin/env python3
"""Admin CLI cho quản lý tokens"""

import argparse
import json
from pathlib import Path

from src.auth.token_verifier import AdminTokenVerifier

TOKENS_FILE = Path("tokens.json")

def load_tokens() -> dict:
    if TOKENS_FILE.exists():
        with open(TOKENS_FILE) as f:
            return json.load(f).get("tokens", {})
    return {}

def save_tokens(tokens: dict):
    with open(TOKENS_FILE, 'w') as f:
        json.dump({"tokens": tokens}, f, indent=2)

def generate_token(user_id: str, secret_key: str):
    tokens = load_tokens()
    verifier = AdminTokenVerifier(secret_key, tokens)
    token = verifier.generate_token(user_id, ["usage:write"])

    tokens[token] = {
        "user_id": user_id,
        "scopes": ["usage:write"],
        "revoked": False,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": None
    }
    save_tokens(tokens)

    print(f"Token generated for {user_id}:")
    print(token)

def revoke_token(token: str):
    tokens = load_tokens()
    if token in tokens:
        tokens[token]["revoked"] = True
        save_tokens(tokens)
        print(f"Token revoked: {token[:20]}...")
    else:
        print("Token not found")

def list_tokens():
    tokens = load_tokens()
    for token, info in tokens.items():
        status = "REVOKED" if info.get("revoked") else "ACTIVE"
        print(f"{token[:20]}... | {info['user_id']} | {status}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Token management CLI")
    subparsers = parser.add_subparsers(dest="command")

    gen_parser = subparsers.add_parser("generate")
    gen_parser.add_argument("user_id")
    gen_parser.add_argument("--secret", required=True)

    revoke_parser = subparsers.add_parser("revoke")
    revoke_parser.add_argument("token")

    subparsers.add_parser("list")

    args = parser.parse_args()

    if args.command == "generate":
        generate_token(args.user_id, args.secret)
    elif args.command == "revoke":
        revoke_token(args.token)
    elif args.command == "list":
        list_tokens()
```

---

## Phần 5: Thiết lập cho Team Members

### 5.1 Hướng dẫn cài đặt cho thành viên

1. **Nhận access token từ admin**
   ```bash
   # Admin chạy:
   python scripts/admin_token.py generate <github_username> --secret $TOKEN_SECRET_KEY
   ```

2. **Cấu hình environment variables**
   ```bash
   # Thêm vào ~/.bashrc hoặc ~/.zshrc
   export MCP_USAGE_ACCESS_TOKEN="your-token-here"
   export MCP_USAGE_SERVER_URL="https://your-mcp-server.com"
   ```

3. **Cài đặt hook**
   ```bash
   # Copy hook script
   mkdir -p ~/.claude/hooks
   cp hooks/send_usage.sh ~/.claude/hooks/
   chmod +x ~/.claude/hooks/send_usage.sh
   ```

4. **Cấu hình Claude Code settings**
   ```bash
   # Thêm vào ~/.claude/settings.json
   {
     "hooks": {
       "Stop": [
         {
           "matcher": "*",
           "hooks": [
             {
               "type": "command",
               "command": "bash ~/.claude/hooks/send_usage.sh",
               "timeout": 30
             }
           ]
         }
       ]
     }
   }
   ```

---

## Phần 6: Viewing Data trong Langfuse

### 6.1 Dashboard Filters

- **Filter by User**: Sử dụng `user_id` (GitHub username)
- **Filter by Project**: Sử dụng `metadata.project_name`
- **Filter by Model**: Sử dụng tags hoặc `model` field
- **Filter by Time**: Sử dụng timestamp range

### 6.2 Metrics có thể theo dõi

1. **Usage per User**: Số prompts, tokens used
2. **Cost Analysis**: Chi phí theo user/project/model
3. **Performance**: Latency trung bình
4. **Popular Models**: Model usage distribution
5. **Active Hours**: Thời gian sử dụng nhiều nhất

---

## Thứ tự Implementation

1. **Phase 1: Core MCP Server**
   - [ ] Setup project structure
   - [ ] Implement data models
   - [ ] Implement token verifier
   - [ ] Implement Langfuse tracer
   - [ ] Create main MCP server với `report_usage` tool

2. **Phase 2: Admin Tools**
   - [ ] Implement token generation
   - [ ] Implement token revocation
   - [ ] Create admin CLI script

3. **Phase 3: Claude Code Hook**
   - [ ] Create hook script (bash/python)
   - [ ] Test với local MCP server
   - [ ] Document cài đặt cho team

4. **Phase 4: Deployment**
   - [ ] Dockerize server
   - [ ] Deploy lên cloud (AWS/GCP/etc.)
   - [ ] Setup monitoring & alerting

5. **Phase 5: Team Rollout**
   - [ ] Generate tokens cho team members
   - [ ] Distribute setup guide
   - [ ] Monitor & troubleshoot

---

## Lưu ý quan trọng

1. **Security**:
   - Token secret key phải được bảo mật
   - Sử dụng HTTPS cho production
   - Không log sensitive data

2. **Privacy**:
   - Cân nhắc anonymize prompt content nếu cần
   - Comply với data retention policies

3. **Performance**:
   - Hook script phải chạy nhanh (< 30s timeout)
   - Langfuse client sử dụng async batching

4. **Reliability**:
   - Hook failures không nên block Claude Code
   - Implement retry logic cho network errors
