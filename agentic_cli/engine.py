import os
import json
import subprocess
import sys
import requests
import time
from datetime import datetime
from typing import Generator, List, Dict, Any, Optional

# Constants
CONFIG_PATH = os.path.expanduser("~/.agentic_cli_config.json")
DEFAULT_MODEL = "qwen/qwen3-coder:free"

class AgentConfig:
    def __init__(self):
        self.load()

    def load(self):
        defaults = self.default_data()
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    loaded = json.load(f)
                # Robust merge
                self.data = defaults
                for key, value in loaded.items():
                    if isinstance(value, dict) and key in self.data:
                        self.data[key].update(value)
                    else:
                        self.data[key] = value
            except:
                self.data = defaults
        else:
            self.data = defaults

    def default_data(self):
        return {
            "backend": "openrouter",
            "auto_approve": False,
            "openrouter": {"model": DEFAULT_MODEL, "key": ""},
            "openai": {"model": "gpt-4o", "key": ""},
            "anthropic": {"model": "claude-3-5-sonnet-20240620", "key": ""},
            "gemini": {"model": "gemini-1.5-pro", "key": ""},
            "opencode_zen": {"model": "big-pickle", "key": ""},
        }

    def save(self):
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)

    @property
    def backend(self):
        b = self.data.get("backend", "openrouter")
        if b not in self.data or not isinstance(self.data[b], dict):
            return "openrouter"
        return b

    @backend.setter
    def backend(self, val): self.data["backend"] = val

    @property
    def current_model(self):
        b = self.backend
        return self.data[b].get("model", "")

    @property
    def auto_approve(self): return self.data.get("auto_approve", False)
    @auto_approve.setter
    def auto_approve(self, val): self.data["auto_approve"] = val

config = AgentConfig()

class AgentEngine:
    def __init__(self):
        self.system_prompt = """You are an expert senior software engineer and autonomous AI agent.
Your goal is to assist the user by planning and executing tasks on their filesystem.

STRICT WORKFLOW RULES:
1. Always start by providing a short "PLAN" of action.
2. Output tool calls using this EXACT format:
<tool>
{"name": "tool_name", "args": {"arg1": "value"}}
</tool>
3. You can issue multiple tool calls in sequence.
4. Continue working until the task is complete. If you are finished, state that you are done.

Available tools: read_file(path), write_file(path, content), execute_command(cmd)"""
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self._last_request_time = 0

    def execute_tool(self, name: str, args: dict) -> str:
        try:
            if name == "read_file":
                path = args.get('path')
                if not path: return "Error: Missing 'path'"
                with open(path, 'r', encoding='utf-8') as f: return f.read()
            elif name == "write_file":
                path = args.get('path')
                content = args.get('content', '')
                if not path: return "Error: Missing 'path'"
                with open(path, 'w', encoding='utf-8') as f: f.write(content)
                return f"Successfully written to {path}"
            elif name == "execute_command":
                cmd = args.get('cmd')
                if not cmd: return "Error: Missing 'cmd'"
                # Longer timeout for mobile execution
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
                return f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
            return f"Error: Unknown tool '{name}'"
        except Exception as e:
            return f"Error executing {name}: {str(e)}"

    def get_completion(self, stream: bool = True) -> Generator[str, None, None]:
        backend = config.backend
        key = config.data[backend]["key"]
        model = config.data[backend]["model"]

        if not key:
            yield f"Error: {backend.upper()} API key not set. Set it in /setup."
            return

        # Rate limiting to respect API tiers
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < 1.0: # 1 request per second max to be safe
            time.sleep(1.0 - elapsed)
        self._last_request_time = time.time()

        url = "https://openrouter.ai/api/v1/chat/completions"
        if backend == "openai": url = "https://api.openai.com/v1/chat/completions"
        elif backend == "anthropic": url = "https://api.anthropic.com/v1/messages"
        elif backend == "gemini": url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        elif backend == "opencode_zen": url = "https://opencode.ai/zen/v1/chat/completions"

        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        if backend == "anthropic":
            headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
            payload = {"model": model, "messages": [m for m in self.messages if m['role'] != 'system'], "system": self.messages[0]['content'], "stream": stream, "max_tokens": 4096}
        else:
            payload = {"model": model, "messages": self.messages, "stream": stream}

        try:
            response = requests.post(url, headers=headers, json=payload, stream=stream, timeout=60)
            response.raise_for_status()

            full_content = ""
            if stream:
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith("data: "):
                            data_str = line_str[6:]
                            if data_str.strip() == "[DONE]": break
                            try:
                                data = json.loads(data_str)
                                if backend == "anthropic":
                                    content = data['delta']['text'] if data['type'] == 'content_block_delta' else ""
                                else:
                                    content = data['choices'][0]['delta'].get('content', '')
                                full_content += content
                                yield full_content
                            except: continue
            else:
                data = response.json()
                full_content = data['content'][0]['text'] if backend == "anthropic" else data['choices'][0]['message']['content']
                yield full_content
        except Exception as e:
            yield f"Inference Error: {str(e)}"
