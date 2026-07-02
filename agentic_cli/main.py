import os
import json
import subprocess
import sys
import requests
import questionary
from gradio_client import Client
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

class AgentConfig:
    def __init__(self):
        self.load()
        self.hf_client = None

    def load(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {
                "backend": "hf",
                "hf": {"repo_id": "taperx/agentic-qwen-cli"},
                "openrouter": {"model": "meta-llama/llama-3.1-70b-instruct", "key": ""},
                "openai": {"model": "gpt-4o", "key": ""},
                "anthropic": {"model": "claude-3-5-sonnet-20240620", "key": ""},
                "gemini": {"model": "gemini-1.5-pro", "key": ""},
            }

    def save(self):
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)

    @property
    def backend(self): return self.data["backend"]
    @backend.setter
    def backend(self, val): self.data["backend"] = val

    def get_current_model(self):
        if self.backend == "hf": return self.data["hf"]["repo_id"]
        return self.data[self.backend]["model"]

    def setup_hf(self):
        if not self.hf_client:
            try:
                repo_id = self.data["hf"]["repo_id"]
                self.hf_client = Client(repo_id)
                return True
            except Exception as e:
                console.print(f"[danger]HF Connection failed: {e}[/danger]")
                return False
        return True

config = AgentConfig()

# ==========================================
# LOCAL ATOMIC TOOLS
# ==========================================

def read_file(path):
    console.print(f"[tool]🔍 Analyzing file:[/tool] [underline]{path}[/underline]")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        console.print(f"[green]✓ Analyzed {len(content.splitlines())} lines of code.[/green]")
        return content
    except Exception as e:
        console.print(f"[danger]✗ Failed to read file: {e}[/danger]")
        return f"Error reading file: {e}"

def write_file(path, content):
    action = "Editing" if os.path.exists(path) else "Creating"
    console.print(f"[tool]💾 {action} file:[/tool] [underline]{path}[/underline]")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        console.print(f"[green]✓ Successfully saved changes to {path}.[/green]")
        return "File written successfully."
    except Exception as e:
        console.print(f"[danger]✗ Failed to write file: {e}[/danger]")
        return f"Error writing file: {e}"

def execute_command(cmd):
    console.print(f"[tool]💻 Running command:[/tool] `[italic]{cmd}[/italic]`")
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if res.returncode == 0:
            console.print("[green]✓ Command executed successfully.[/green]")
        else:
            console.print(f"[warning]⚠ Command exited with code {res.returncode}.[/warning]")
        return f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    except subprocess.TimeoutExpired:
        console.print("[danger]✗ Command timed out after 30 seconds.[/danger]")
        return "Error: Command timed out."
    except Exception as e:
        console.print(f"[danger]✗ Error executing command: {e}[/danger]")
        return f"Error executing command: {e}"

# ==========================================
# INFERENCE BACKENDS
# ==========================================

def get_hf_completion(messages):
    if not config.setup_hf():
        yield "Error: Could not connect to Hugging Face Space."
        return
    prompt = "".join([f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages])
    prompt += "<|im_start|>assistant\n"
    try:
        try:
            job = config.hf_client.submit(prompt, api_name="/predict")
        except ValueError:
            job = config.hf_client.submit(prompt, api_name="predict")
        for text_chunk in job:
            if isinstance(text_chunk, str): yield text_chunk
    except Exception as e: yield f"Error during HF inference: {e}"

def get_openai_style_completion(url, key, model, messages, provider_name):
    if not key:
        yield f"Error: API key for {provider_name} not set. Use /setup to configure."
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
        yield "Error: Anthropic API key not set. Use /setup to configure."
        return
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    # Convert messages to Anthropic format
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

def get_gemini_completion(messages):
    key = config.data["gemini"]["key"]
    model = config.data["gemini"]["model"]
    if not key:
        yield "Error: Gemini API key not set. Use /setup to configure."
        return
    # Very basic gemini implementation via their OpenAI-compatible endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    return get_openai_style_completion(url, key, model, messages, "Gemini")

# ==========================================
# INTERACTIVE SETUP
# ==========================================

def interactive_setup():
    choice = questionary.select(
        "What would you like to configure?",
        choices=["Switch Backend", "Set API Keys", "Change Models", "Hugging Face Repo ID", "Back"]
    ).ask()

    if choice == "Switch Backend":
        config.backend = questionary.select(
            "Select backend:",
            choices=["hf", "openrouter", "openai", "anthropic", "gemini"]
        ).ask()
        console.print(f"[green]Backend switched to {config.backend}[/green]")

    elif choice == "Set API Keys":
        provider = questionary.select(
            "Select provider:",
            choices=["openrouter", "openai", "anthropic", "gemini"]
        ).ask()
        key = questionary.password(f"Enter API key for {provider}:").ask()
        if key:
            config.data[provider]["key"] = key
            console.print(f"[green]Key for {provider} saved.[/green]")

    elif choice == "Change Models":
        provider = questionary.select(
            "Select provider to change model:",
            choices=["openrouter", "openai", "anthropic", "gemini"]
        ).ask()
        new_model = questionary.text(f"Enter new model for {provider}:", default=config.data[provider]["model"]).ask()
        config.data[provider]["model"] = new_model
        console.print(f"[green]Model for {provider} set to {new_model}[/green]")

    elif choice == "Hugging Face Repo ID":
        new_repo = questionary.text("Enter HF Repo ID:", default=config.data["hf"]["repo_id"]).ask()
        config.data["hf"]["repo_id"] = new_repo
        config.hf_client = None
        console.print(f"[green]HF Repo ID set to {new_repo}[/green]")

    config.save()

# ==========================================
# CHAT LOOP
# ==========================================

def chat_loop():
    console.print(Panel(Text("Agentic CLI: Local Assistant", style="bold white", justify="center"), style="blue"))

    system_prompt = """You are "Jules," an expert senior software engineer and autonomous coding agent.
Your goal is to assist the user by reading, writing, and executing code on their local filesystem.

STRICT TOOL RULES:
1. ONLY use the tools listed below.
2. Output EXACTLY this format for tools:
<tool>
{"name": "tool_name", "args": {"arg1": "value"}}
</tool>
3. Do NOT hallucinate paths. Only use paths that exist or that the user has specified.
4. After calling a tool, WAIT for the user to provide the result before continuing.
5. Respond with regular Markdown if no tool is needed.

Available tools:
- read_file(path)
- write_file(path, content)
- execute_command(cmd)"""

    messages = [{"role": "system", "content": system_prompt}]
    console.print("\n[bold green]🤖 Jules is ready.[/bold green] Type 'exit' to quit.")
    console.print("[info]Commands: /setup, /status, /clear, exit[/info]")

    while True:
        try:
            curr_info = f"({config.backend}:{config.get_current_model()})"
            user_input = console.input(f"\n[user]user {curr_info}[/user] > ")

            if not user_input.strip(): continue
            if user_input.lower() in ['exit', 'quit']: break

            if user_input.startswith("/"):
                cmd = user_input.split()[0].lower()
                if cmd == "/setup": interactive_setup()
                elif cmd == "/status":
                    table = Table(title="Agent Configuration")
                    table.add_column("Provider", style="cyan")
                    table.add_column("Current Model", style="magenta")
                    table.add_column("Key Set", style="green")
                    for p in ["hf", "openrouter", "openai", "anthropic", "gemini"]:
                        is_curr = "[bold yellow]*[/bold yellow] " if config.backend == p else ""
                        model = config.data[p]["repo_id"] if p == "hf" else config.data[p]["model"]
                        key_set = "N/A" if p == "hf" else ("Yes" if config.data[p]["key"] else "No")
                        table.add_row(f"{is_curr}{p}", model, key_set)
                    console.print(table)
                elif cmd == "/clear":
                    messages = [{"role": "system", "content": system_prompt}]
                    console.print("[info]Conversation cleared.[/info]")
                else: console.print("[danger]Unknown command.[/danger]")
                continue

            messages.append({"role": "user", "content": user_input})

            while True:
                response_text = ""
                if config.backend == "hf": gen = get_hf_completion(messages)
                elif config.backend == "openrouter":
                    gen = get_openai_style_completion("https://openrouter.ai/api/v1/chat/completions", config.data["openrouter"]["key"], config.data["openrouter"]["model"], messages, "OpenRouter")
                elif config.backend == "openai":
                    gen = get_openai_style_completion("https://api.openai.com/v1/chat/completions", config.data["openai"]["key"], config.data["openai"]["model"], messages, "OpenAI")
                elif config.backend == "anthropic": gen = get_anthropic_completion(messages)
                elif config.backend == "gemini": gen = get_gemini_completion(messages)

                with Live(Spinner("dots", text=f"Jules thinking...", style="cyan"), refresh_per_second=10, console=console, transient=True) as live:
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
