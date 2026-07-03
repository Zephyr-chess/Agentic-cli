import os
import json
import subprocess
import sys
import requests
import questionary
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme
from rich.table import Table

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
DEFAULT_MODEL = "qwen/qwen3-coder:free"
NEMOTRON_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"

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
            "openrouter": {"model": DEFAULT_MODEL, "key": ""},
            "openai": {"model": "gpt-4o", "key": ""},
            "anthropic": {"model": "claude-3-5-sonnet-20240620", "key": ""},
            "gemini": {"model": "gemini-1.5-pro", "key": ""},
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

config = AgentConfig()

# ==========================================
# LOCAL ATOMIC TOOLS
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
# INFERENCE BACKENDS
# ==========================================

def get_openai_style_completion(url, key, model, messages, provider_name):
    if not key:
        yield f"Error: {provider_name} API key not set. Use /setup."
        return
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "stream": True}
    try:
        response = requests.post(url, headers=headers, json=payload, stream=True)
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
    except Exception as e: yield f"Error during {provider_name} inference: {e}"

def get_anthropic_completion(messages):
    key = config.data["anthropic"]["key"]
    model = config.data["anthropic"]["model"]
    if not key:
        yield "Error: Anthropic API key not set. Use /setup."
        return
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    system_msg = next((m['content'] for m in messages if m['role'] == 'system'), "")
    anth_messages = [m for m in messages if m['role'] != 'system']

    payload = {
        "model": model,
        "system": system_msg,
        "messages": anth_messages,
        "stream": True,
        "max_tokens": 4096
    }
    try:
        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, stream=True)
        response.raise_for_status()
        full_content = ""
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    try:
                        data = json.loads(line_str[6:])
                        if data['type'] == 'content_block_delta':
                            full_content += data['delta']['text']
                            yield full_content
                    except: continue
    except Exception as e: yield f"Error during Anthropic inference: {e}"

# ==========================================
# INTERACTIVE SETUP
# ==========================================

def interactive_setup():
    choice = questionary.select(
        "Agent Setup",
        choices=["Switch Backend", "Set API Keys", "Change Models", "Use Nemotron Free", "Back"]
    ).ask()

    if choice == "Switch Backend":
        config.backend = questionary.select(
            "Select provider:",
            choices=["openrouter", "openai", "anthropic", "gemini"]
        ).ask()
        console.print(f"[green]Switched to {config.backend}[/green]")

    elif choice == "Set API Keys":
        provider = questionary.select(
            "Set key for:",
            choices=["openrouter", "openai", "anthropic", "gemini"]
        ).ask()
        key = questionary.password(f"Enter key for {provider}:").ask()
        if key:
            config.data[provider]["key"] = key
            console.print(f"[green]Key saved.[/green]")

    elif choice == "Change Models":
        provider = questionary.select(
            "Set model for:",
            choices=["openrouter", "openai", "anthropic", "gemini"]
        ).ask()
        model = questionary.text(f"Enter model:", default=config.data[provider]["model"]).ask()
        config.data[provider]["model"] = model
        console.print(f"[green]Model updated.[/green]")

    elif choice == "Use Nemotron Free":
        config.backend = "openrouter"
        config.data["openrouter"]["model"] = NEMOTRON_MODEL
        console.print(f"[green]Set to {NEMOTRON_MODEL}[/green]")

    config.save()

# ==========================================
# CHAT LOOP
# ==========================================

def chat_loop():
    console.print(Panel(Text("Agentic CLI: Local Assistant", style="bold white", justify="center"), style="blue"))

    system_prompt = """You are "Jules," an expert software engineer.
Your goal is to assist the user by reading, writing, and executing code on their filesystem.

STRICT TOOL RULES:
1. Output EXACTLY this format:
<tool>
{"name": "tool_name", "args": {"arg1": "value"}}
</tool>
2. After a tool call, WAIT for the result.

Available: read_file(path), write_file(path, content), execute_command(cmd)"""

    messages = [{"role": "system", "content": system_prompt}]
    console.print("\n[bold green]🤖 Ready.[/bold green] Type 'exit' to quit. Commands: /setup, /status, /clear")

    while True:
        try:
            current = f"({config.backend}:{config.current_model})"
            user_input = console.input(f"\n[user]user {current}[/user] > ")

            if not user_input.strip(): continue
            if user_input.lower() in ['exit', 'quit']: break

            if user_input.startswith("/"):
                cmd = user_input.split()[0].lower()
                if cmd == "/setup": interactive_setup()
                elif cmd == "/status":
                    table = Table(title="Configuration Status")
                    table.add_column("Provider", style="cyan")
                    table.add_column("Model", style="magenta")
                    table.add_column("Key", style="green")
                    for p in ["openrouter", "openai", "anthropic", "gemini"]:
                        is_curr = "*" if config.backend == p else ""
                        table.add_row(f"{is_curr}{p}", config.data[p]["model"], "Yes" if config.data[p]["key"] else "No")
                    console.print(table)
                elif cmd == "/clear":
                    messages = [{"role": "system", "content": system_prompt}]
                    console.print("[info]Chat cleared.[/info]")
                continue

            messages.append({"role": "user", "content": user_input})

            while True:
                response_text = ""
                if config.backend == "openrouter":
                    gen = get_openai_style_completion("https://openrouter.ai/api/v1/chat/completions", config.data["openrouter"]["key"], config.data["openrouter"]["model"], messages, "OpenRouter")
                elif config.backend == "openai":
                    gen = get_openai_style_completion("https://api.openai.com/v1/chat/completions", config.data["openai"]["key"], config.data["openai"]["model"], messages, "OpenAI")
                elif config.backend == "anthropic":
                    gen = get_anthropic_completion(messages)
                elif config.backend == "gemini":
                    gen = get_openai_style_completion("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", config.data["gemini"]["key"], config.data["gemini"]["model"], messages, "Gemini")

                with Live(Spinner("dots", text="Thinking...", style="cyan"), refresh_per_second=10, console=console, transient=True) as live:
                    for text_chunk in gen:
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
                        messages.append({"role": "user", "content": f"Tool Result:\n{result}"})
                    except Exception as e:
                        console.print(f"[danger]Error: {e}[/danger]")
                        messages.append({"role": "assistant", "content": response_text})
                        messages.append({"role": "user", "content": f"Error: {e}"})
                else:
                    console.print(Markdown(response_text))
                    messages.append({"role": "assistant", "content": response_text})
                    break
        except KeyboardInterrupt: break

def main():
    chat_loop()

if __name__ == "__main__":
    main()
