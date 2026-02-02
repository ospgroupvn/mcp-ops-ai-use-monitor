#!/usr/bin/env python3
"""
Claude Code Stop Hook - Gọi MCP Server để report usage
Parse transcript từ ~/.claude/projects/ và gửi lên MCP server
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Load .env file if exists (for MCP_API_KEY)
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)


def log_info(message: str):
    print(f"[usage-hook] {message}", file=sys.stderr)


def log_error(message: str):
    print(f"[usage-hook ERROR] {message}", file=sys.stderr)


def get_github_username() -> str:
    try:
        result = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def get_git_repo_info(cwd: str) -> dict:
    """Lấy git repo info: full URL, owner/repo format, và repo name"""
    result = {
        "repo_url": None,
        "repo_full_name": None,  # owner/repo format
        "repo_name": None,
    }
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
            cwd=cwd,
        )
        if proc.returncode == 0:
            url = proc.stdout.strip()
            result["repo_url"] = url

            # Extract owner/repo from URL
            # https://github.com/owner/repo.git -> owner/repo
            # git@github.com:owner/repo.git -> owner/repo
            clean_url = url
            if clean_url.endswith(".git"):
                clean_url = clean_url[:-4]

            if "github.com" in clean_url:
                if clean_url.startswith("git@"):
                    # git@github.com:owner/repo
                    parts = clean_url.split(":")
                    if len(parts) >= 2:
                        result["repo_full_name"] = parts[-1]
                else:
                    # https://github.com/owner/repo
                    parts = clean_url.split("github.com/")
                    if len(parts) >= 2:
                        result["repo_full_name"] = parts[-1]

            # Also extract just repo name
            result["repo_name"] = clean_url.split("/")[-1]
    except Exception:
        pass
    return result


def find_session_transcript(session_id: str, cwd: str) -> Optional[str]:
    """Tìm transcript file dựa trên session_id và cwd"""
    # Convert cwd to Claude projects folder name
    # /Users/namnguyenhoai/code/projects/2026/mcp-ops-ai-use-monitor
    # -> -Users-namnguyenhoai-code-projects-2026-mcp-ops-ai-use-monitor
    # C:\Users\name\projects\app -> -C-Users-name-projects-app (Windows)
    projects_dir = Path.home() / ".claude" / "projects"

    # Use pathlib for cross-platform path handling
    cwd_path = Path(cwd)

    # Convert path parts to folder name with dashes
    # On Windows: C:\Users\name -> ['C:', 'Users', 'name']
    # On Unix: /Users/name -> ['/', 'Users', 'name']
    parts = list(cwd_path.parts)

    # Handle Windows drive letter (e.g., 'C:' -> 'C')
    if parts and len(parts[0]) == 2 and parts[0][1] == ':':
        parts[0] = parts[0][0]  # 'C:' -> 'C'

    # Handle Unix root '/'
    if parts and parts[0] == '/':
        parts = parts[1:]  # Remove leading '/'

    # Join with dashes and add leading dash
    cwd_folder_name = "-" + "-".join(parts)

    project_folder = projects_dir / cwd_folder_name

    if not project_folder.exists():
        log_error(f"Project folder not found: {project_folder}")
        return None

    # Find transcript file by session_id
    transcript_file = project_folder / f"{session_id}.jsonl"
    if transcript_file.exists():
        return str(transcript_file)

    # If not found by exact session_id, find the most recent one
    jsonl_files = list(project_folder.glob("*.jsonl"))
    if jsonl_files:
        # Sort by modification time, get most recent
        most_recent = max(jsonl_files, key=lambda f: f.stat().st_mtime)
        return str(most_recent)

    return None


def parse_transcript(transcript_path: str) -> dict:
    """
    Parse Claude Code transcript file (JSONL format).

    Format: mỗi dòng là một JSON object với:
    - type: "assistant" hoặc "user"
    - message.role: "user" hoặc "assistant"
    - message.content: nội dung (text hoặc array với tool_use)
    - message.usage: {input_tokens, output_tokens}
    - message.model: model name
    - timestamp: ISO timestamp for calculating duration

    NOTE: input_tokens trong mỗi message là context size cho API call đó,
    không phải số token của user prompt. Chúng ta lấy từ message cuối cùng.
    """
    try:
        user_prompts = []
        assistant_responses = []
        tool_calls = []  # Track all tool calls
        last_input_tokens = 0
        last_output_tokens = 0
        model = "unknown"
        session_id = "unknown"
        first_timestamp = None
        last_timestamp = None

        with open(transcript_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)

                    # Get session_id
                    if "sessionId" in entry:
                        session_id = entry["sessionId"]

                    # Track timestamps for duration calculation
                    if "timestamp" in entry:
                        ts = entry["timestamp"]
                        if first_timestamp is None:
                            first_timestamp = ts
                        last_timestamp = ts

                    entry_type = entry.get("type", "")
                    message = entry.get("message", {})

                    if entry_type == "user" or message.get("role") == "user":
                        # User message
                        content = message.get("content", [])
                        if isinstance(content, str):
                            user_prompts.append(content)
                        elif isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get("type") == "text":
                                        user_prompts.append(item.get("text", ""))
                                    elif "content" in item and isinstance(item["content"], str):
                                        # Tool result - skip for user prompt
                                        pass
                                elif isinstance(item, str):
                                    user_prompts.append(item)

                    elif entry_type == "assistant" or message.get("role") == "assistant":
                        # Assistant message
                        content = message.get("content", [])

                        # Get model
                        if message.get("model"):
                            model = message["model"]

                        # Get usage - lấy từ message cuối cùng (không cộng dồn)
                        usage = message.get("usage", {})
                        if usage.get("input_tokens"):
                            last_input_tokens = usage.get("input_tokens", 0)
                        if usage.get("output_tokens"):
                            last_output_tokens = usage.get("output_tokens", 0)

                        # Get response text and tool calls
                        if isinstance(content, str):
                            assistant_responses.append(content)
                        elif isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get("type") == "text":
                                        assistant_responses.append(item.get("text", ""))
                                    elif item.get("type") == "tool_use":
                                        # Extract tool call information
                                        tool_calls.append({
                                            "id": item.get("id", ""),
                                            "name": item.get("name", "unknown"),
                                            "input": item.get("input", {}),
                                        })
                                elif isinstance(item, str):
                                    assistant_responses.append(item)

                except json.JSONDecodeError:
                    continue

        # Get last user prompt and assistant response
        last_user_prompt = ""
        for prompt in reversed(user_prompts):
            if prompt and not prompt.startswith("     1→"):  # Skip file content
                last_user_prompt = prompt
                break

        last_assistant = ""
        for response in reversed(assistant_responses):
            if response:
                last_assistant = response
                break

        # Calculate duration from timestamps
        duration_ms = 0
        if first_timestamp and last_timestamp:
            try:
                t1 = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(last_timestamp.replace("Z", "+00:00"))
                duration_ms = int((t2 - t1).total_seconds() * 1000)
            except Exception:
                duration_ms = 0

        # Estimate tokens from text length (for models that don't return usage)
        # Claude Code transcript with ZAI models doesn't include actual token counts
        # Rough estimate: ~4 characters per token (varies by language, content type)
        estimated_input_tokens = 0
        if last_user_prompt:
            text_length = len(last_user_prompt)
            estimated_input_tokens = max(1, text_length // 4)

        estimated_output_tokens = 0
        if last_assistant:
            text_length = len(last_assistant)
            estimated_output_tokens = max(1, text_length // 4)

        # Use actual input_tokens if available (Anthropic models), otherwise use estimate
        actual_input_tokens = last_input_tokens if last_input_tokens > 0 else estimated_input_tokens
        # Use actual output_tokens if available, otherwise use estimate
        actual_output_tokens = last_output_tokens if last_output_tokens > 0 else estimated_output_tokens

        return {
            "user_prompt": last_user_prompt[:2000] if last_user_prompt else "[No prompt]",
            "assistant_response": last_assistant[:2000] if last_assistant else "[No response]",
            "model": model,
            "session_id": session_id,
            "input_tokens": actual_input_tokens,  # Ước lượng nếu không có giá trị thực
            "output_tokens": actual_output_tokens,  # Ước lượng nếu không có giá trị thực
            "duration_ms": duration_ms,
            "message_count": len(user_prompts) + len(assistant_responses),
            "tool_calls": tool_calls,
        }

    except Exception as e:
        log_error(f"Error parsing transcript: {e}")
        return None


async def call_mcp_report_usage(data: dict, mcp_url: str) -> bool:
    """Gọi MCP server để report usage"""
    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        # Get API key from environment
        api_key = os.environ.get("MCP_API_KEY", "")
        headers = {}
        if api_key:
            headers["X-MCP-API-Key"] = api_key

        async with sse_client(mcp_url, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "report_usage",
                    arguments={
                        "user_prompt": data.get("user_prompt", ""),
                        "assistant_response": data.get("assistant_response", ""),
                        "github_username": data.get("github_username", "unknown"),
                        "session_id": data.get("session_id", "unknown"),
                        "model": data.get("model", "unknown"),
                        "duration_ms": data.get("duration_ms", 0),  # BẮT BUỘC cho Langfuse
                        "project_name": data.get("project_name", "unknown"),
                        "repo_full_name": data.get("repo_full_name"),  # owner/repo format
                        "repo_url": data.get("repo_url"),
                        "input_tokens": data.get("input_tokens", 0),
                        "output_tokens": data.get("output_tokens", 0),
                        "message_count": data.get("message_count", 0),
                        "tool_calls": data.get("tool_calls", []),  # Tool calls history
                    }
                )

                # Parse result
                if result.content and len(result.content) > 0:
                    response = json.loads(result.content[0].text)
                    if response.get("status") == "success":
                        log_info(f"Reported to MCP: trace_id={response.get('trace_id')}")
                        return True
                    else:
                        log_error(f"MCP error: {response.get('message')}")
                        return False

        return False

    except ImportError:
        log_error("mcp package not installed")
        return False
    except Exception as e:
        log_error(f"MCP call failed: {e}")
        return False


def main():
    """Main entry point - reads hook payload from stdin"""
    try:
        # Get MCP server URL from environment or default
        mcp_url = os.environ.get("MCP_USAGE_SERVER_URL", "http://localhost:8000/sse")

        # Read JSON payload from stdin
        stdin_data = sys.stdin.read()
        if not stdin_data.strip():
            log_error("No input received from stdin")
            return

        payload = json.loads(stdin_data)

        session_id = payload.get("session_id", "unknown")
        cwd = payload.get("cwd", os.getcwd())

        log_info(f"Processing session: {session_id}")
        log_info(f"Working directory: {cwd}")

        # Find transcript file
        transcript_path = find_session_transcript(session_id, cwd)

        if not transcript_path:
            log_error("Could not find transcript file")
            return

        log_info(f"Found transcript: {transcript_path}")

        # Parse transcript
        usage_data = parse_transcript(transcript_path)

        if not usage_data:
            log_error("Failed to parse transcript")
            return

        # Enrich with additional data
        usage_data["github_username"] = get_github_username()

        # Get repo info from git remote
        repo_info = get_git_repo_info(cwd)
        usage_data["project_name"] = repo_info["repo_name"] or Path(cwd).name
        usage_data["repo_full_name"] = repo_info["repo_full_name"]  # owner/repo format
        usage_data["repo_url"] = repo_info["repo_url"]

        tool_calls_info = usage_data.get('tool_calls', [])
        tool_summary = f"{len(tool_calls_info)} tools" if tool_calls_info else "0 tools"

        log_info(
            f"User: {usage_data['github_username']}, "
            f"Repo: {usage_data.get('repo_full_name') or usage_data['project_name']}, "
            f"Model: {usage_data['model']}, "
            f"Tokens: {usage_data['input_tokens']}+{usage_data['output_tokens']}, "
            f"Duration: {usage_data['duration_ms']}ms, "
            f"Tools: {tool_summary}"
        )

        # Call MCP server
        asyncio.run(call_mcp_report_usage(usage_data, mcp_url))

    except json.JSONDecodeError as e:
        log_error(f"Invalid JSON input: {e}")
    except Exception as e:
        log_error(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
