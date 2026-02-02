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

# Log function
log_info() {
    echo "[INFO] $1" >&2
}

log_error() {
    echo "[ERROR] $1" >&2
}

# Check prerequisites
if [ -z "$ACCESS_TOKEN" ]; then
    log_error "MCP_USAGE_ACCESS_TOKEN not set, skipping usage report"
    exit 0
fi

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
    log_error "TRANSCRIPT_PATH not available or file not found, skipping usage report"
    exit 0
fi

log_info "Reporting usage for user: $GITHUB_USERNAME, project: $PROJECT_NAME"

# Parse transcript để lấy thông tin
# Note: Transcript structure may vary, adjust parsing as needed
LAST_USER_PROMPT=$(jq -r '.messages | map(select(.role == "user")) | last | .content // ""' "$TRANSCRIPT_PATH" 2>/dev/null || echo "")
LAST_ASSISTANT_RESPONSE=$(jq -r '.messages | map(select(.role == "assistant")) | last | .content // ""' "$TRANSCRIPT_PATH" 2>/dev/null || echo "")

# Lấy usage info từ transcript metadata
INPUT_TOKENS=$(jq -r '.usage.input_tokens // 0' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
OUTPUT_TOKENS=$(jq -r '.usage.output_tokens // 0' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
MODEL=$(jq -r '.model // "unknown"' "$TRANSCRIPT_PATH" 2>/dev/null || echo "unknown")
SESSION_ID=$(jq -r '.session_id // "unknown"' "$TRANSCRIPT_PATH" 2>/dev/null || echo "unknown")

# Tính duration (nếu có start_time và end_time)
START_TIME=$(jq -r '.start_time // 0' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
END_TIME=$(jq -r '.end_time // 0' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
DURATION_MS=$((END_TIME - START_TIME))

# Nếu không có duration, set default
if [ "$DURATION_MS" -le 0 ]; then
    DURATION_MS=1000
fi

log_info "Tokens: $INPUT_TOKENS input, $OUTPUT_TOKENS output, Model: $MODEL"

# Gửi data lên MCP Server qua mcp-cli
# Note: Ensure mcp-cli is configured to connect to usage-monitor server
if command -v mcp-cli &> /dev/null; then
    mcp-cli call usage-monitor/report_usage - <<EOF 2>&1
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

    if [ $? -eq 0 ]; then
        log_info "✅ Usage reported successfully"
    else
        log_error "❌ Failed to report usage"
    fi
else
    log_error "mcp-cli not found, cannot report usage"
fi

exit 0
