import os
import json
import subprocess
import sys
import requests
import time
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme
from rich.table import Table

# Theme & Console
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "danger": "bold red",
    "user": "bold green",
    "assistant": "bold blue",
    "tool": "bold yellow",
    "plan": "bold yellow italic",
})
console = Console(theme=custom_theme)

# Configuration
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
        }

    def save(self):
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)

    @property
    def backend(self):
        b = self.data.get("backend", "openrouter")
        return b if b in self.data else "openrouter"

    @property
    def current_model(self):
        return self.data[self.backend].get("model", "")

config = AgentConfig()

# Tools
def execute_tool(name, args):
    if name == "read_file":
        console.print(f"[tool]🔍 Reading:[/tool] [underline]{args['path']}[/underline]")
        with open(args['path'], 'r', encoding='utf-8') as f: return f.read()
    elif name == "write_file":
        console.print(f"[tool]💾 Saving:[/tool] [underline]{args['path']}[/underline]")
        with open(args['path'], 'w', encoding='utf-8') as f: f.write(args['content'])
        return "Success"
    elif name == "execute_command":
        console.print(f"[tool]💻 Executing:[/tool] `[italic]{args['cmd']}[/italic]`")
        res = subprocess.run(args['cmd'], shell=True, capture_output=True, text=True, timeout=60)
        return f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    return "Unknown tool"

# Inference
def get_completion(messages):
    backend = config.backend
    key = config.data[backend]["key"]
    model = config.data[backend]["model"]

    if not key:
        console.print(f"[danger]API key for {backend} not found in {CONFIG_PATH}[/danger]")
        return None

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "stream": True}

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, stream=True)
        response.raise_for_status()

        full_text = ""
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str.strip() == "[DONE]": break
                    try:
                        data = json.loads(data_str)
                        content = data['choices'][0]['delta'].get('content', '')
                        full_text += content
                        yield full_text
                    except: continue
    except Exception as e:
        console.print(f"[danger]Error: {e}[/danger]")
        return None

# Chat Loop
def chat_loop():
    if not config.data["openrouter"]["key"]:
        console.print(Panel("Welcome! Please enter your OpenRouter API Key to start.", style="blue"))
        key = input("OpenRouter Key > ").strip()
        if key:
            config.data["openrouter"]["key"] = key
            config.save()
        else: return

    console.print(Panel(Text(f"Agentic CLI | {config.current_model}", style="bold white", justify="center"), border_style="blue"))

    system_prompt = """You are Jules, an expert senior software engineer.
Your goal is to assist the user by reading, writing, and executing code on their filesystem.

STRICT TOOL RULES:
1. Output tool calls using EXACTLY this format:
<tool>
{"name": "tool_name", "args": {"arg1": "value"}}
</tool>
2. Provide a short PLAN before acting.
3. You can call multiple tools. Wait for results after each turn.

Available: read_file(path), write_file(path, content), execute_command(cmd)"""

    messages = [{"role": "system", "content": system_prompt}]
    console.print("[info]Ready. Type 'exit' to quit. Use '--web' to launch browser UI.[/info]")

    while True:
        try:
            user_input = console.input(f"\n[user]user[/user] > ")
            if not user_input.strip(): continue
            if user_input.lower() in ['exit', 'quit']: break

            messages.append({"role": "user", "content": user_input})

            while True:
                response_text = ""
                with Live(Spinner("dots", text="Thinking...", style="cyan"), refresh_per_second=10, console=console, transient=True) as live:
                    for text_chunk in get_completion(messages):
                        response_text = text_chunk
                        if "<tool>" not in response_text: live.update(Markdown(response_text))
                        else: live.update(Text(response_text))

                if not response_text: break

                messages.append({"role": "assistant", "content": response_text})

                if "<tool>" in response_text:
                    parts = response_text.split("<tool>")
                    if parts[0].strip(): console.print(Markdown(parts[0].strip()))

                    tool_calls = response_text.split("<tool>")[1:]
                    tool_results = []

                    for call in tool_calls:
                        try:
                            tool_str = call.split("</tool>")[0].strip()
                            tool_data = json.loads(tool_str)
                            name, args = tool_data.get("name"), tool_data.get("args", {})

                            # Simple confirmation
                            if not config.data.get("auto_approve"):
                                confirm = console.input(f"\n[warning]Approve {name}({list(args.keys())})? [y/N][/warning] ")
                                if confirm.lower() != 'y':
                                    tool_results.append(f"Tool {name} rejected by user.")
                                    continue

                            res = execute_tool(name, args)
                            tool_results.append(f"Result of {name}: {res}")
                        except Exception as e:
                            tool_results.append(f"Error calling tool: {e}")

                    messages.append({"role": "user", "content": "\n\n".join(tool_results)})
                else:
                    console.print(Markdown(response_text))
                    break
        except KeyboardInterrupt: break

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--web":
        from agentic_cli.web.server import run_web_ui
        run_web_ui()
    else:
        chat_loop()

if __name__ == "__main__":
    main()
