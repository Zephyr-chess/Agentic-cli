import os
import json
import subprocess
import sys
import requests
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme

# Custom theme for Claude-like feel
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "danger": "bold red",
    "user": "bold green",
    "assistant": "bold blue",
    "tool": "bold yellow",
})

console = Console(theme=custom_theme)

CONFIG_PATH = os.path.expanduser("~/.agentic_cli_config.json")
DEFAULT_MODEL = "qwen/qwen-2-72b-instruct:free" # Using the high-performance free Qwen model

class AgentConfig:
    def __init__(self):
        self.load()

    def load(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {
                "openrouter_key": "",
                "model": DEFAULT_MODEL
            }

    def save(self):
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)

    @property
    def key(self): return self.data.get("openrouter_key")
    @key.setter
    def key(self, val): self.data["openrouter_key"] = val

    @property
    def model(self): return self.data.get("model", DEFAULT_MODEL)

config = AgentConfig()

# ==========================================
# LOCAL TOOLS
# ==========================================

def read_file(path):
    console.print(f"[tool]🔍 Analyzing file:[/tool] [underline]{path}[/underline]")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(path, content):
    console.print(f"[tool]💾 Saving file:[/tool] [underline]{path}[/underline]")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return "File written successfully."
    except Exception as e:
        return f"Error writing file: {e}"

def execute_command(cmd):
    console.print(f"[tool]💻 Running command:[/tool] `[italic]{cmd}[/italic]`")
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        return f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# INFERENCE
# ==========================================

def get_completion(messages):
    if not config.key:
        yield "Error: OpenRouter API key not set."
        return

    headers = {
        "Authorization": f"Bearer {config.key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/taperx/agentic-cli",
    }

    payload = {
        "model": config.model,
        "messages": messages,
        "stream": True
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            stream=True
        )
        response.raise_for_status()

        full_content = ""
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str.strip() == "[DONE]": break
                    try:
                        data = json.loads(data_str)
                        content = data['choices'][0]['delta'].get('content', '')
                        full_content += content
                        yield full_content
                    except: continue
    except Exception as e:
        yield f"Error: {e}"

# ==========================================
# CHAT LOOP
# ==========================================

def chat_loop():
    if not config.key:
        console.print(Panel("Welcome to Agentic CLI! Please set your OpenRouter API Key.", style="blue"))
        key = console.input("[bold yellow]Enter OpenRouter Key:[/bold yellow] ")
        if key:
            config.key = key
            config.save()
        else:
            return

    console.print(Panel(Text(f"Agentic CLI: {config.model}", style="bold white", justify="center"), style="blue"))

    system_prompt = f"""You are "Jules," an expert senior software engineer and autonomous coding agent.
Your goal is to assist the user by reading, writing, and executing code on their local filesystem (Termux).

STRICT TOOL RULES:
1. Output EXACTLY this format for tools:
<tool>
{{"name": "tool_name", "args": {{"arg1": "value"}}}}
</tool>
2. After calling a tool, WAIT for the user to provide the result.

Available tools:
- read_file(path)
- write_file(path, content)
- execute_command(cmd)"""

    messages = [{"role": "system", "content": system_prompt}]
    console.print("\n[bold green]🤖 Ready.[/bold green] Type 'exit' to quit.")

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

                if "<tool>" in response_text:
                    try:
                        parts = response_text.split("<tool>")
                        if parts[0].strip(): console.print(Markdown(parts[0].strip()))
                        tool_str = parts[1].split("</tool>")[0].strip()
                        tool_data = json.loads(tool_str)
                        name, args = tool_data.get("name"), tool_data.get("args", {})

                        if name == "read_file": result = read_file(**args)
                        elif name == "write_file": result = write_file(**args)
                        elif name == "execute_command": result = execute_command(**args)
                        else: result = "Tool not found."

                        messages.append({"role": "assistant", "content": response_text})
                        messages.append({"role": "user", "content": f"Tool execution result:\n{result}"})
                    except Exception as e:
                        console.print(f"[danger]Tool Error: {e}[/danger]")
                        messages.append({"role": "assistant", "content": response_text})
                        messages.append({"role": "user", "content": f"Tool Error: {e}"})
                else:
                    console.print(Markdown(response_text))
                    messages.append({"role": "assistant", "content": response_text})
                    break
        except KeyboardInterrupt: break

def main():
    chat_loop()

if __name__ == "__main__":
    main()
