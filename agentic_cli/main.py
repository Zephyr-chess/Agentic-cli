import os
import json
import subprocess
import sys
from gradio_client import Client
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
REPO_ID = "taperx/agentic-qwen-cli"

# ==========================================
# LOCAL ATOMIC TOOLS (EXPLICIT LOGGING UI)
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
# AGENT INTERACTION LOOP
# ==========================================

def chat_loop():
    console.print(Panel(Text("Agentic CLI: Local Assistant", style="bold white", justify="center"), style="blue"))
    console.print(f"[info]Connecting to Hugging Face Space: {REPO_ID}...[/info]")

    try:
        client = Client(REPO_ID)
    except Exception as e:
        console.print(f"[danger]Could not connect. Ensure Space is running on HF. Error: {e}[/danger]")
        return

    system_prompt = """You are "Jules," an expert senior software engineer and autonomous coding agent.
Your goal is to assist the user by reading, writing, and executing code on their local filesystem.

If you need to perform an action, output EXACTLY this JSON format and NOTHING else:
<tool>
{"name": "tool_name", "args": {"arg1": "value"}}
</tool>

Available tools:
1. read_file (args: "path")
2. write_file (args: "path", "content")
3. execute_command (args: "cmd")

Wait for the user to provide the tool result before continuing. If no tool is required, respond with regular text.
Always use Markdown for your responses when not using a tool."""

    messages = [{"role": "system", "content": system_prompt}]
    console.print("\n[bold green]🤖 Jules is ready.[/bold green] Type 'exit' to quit.")

    while True:
        try:
            user_input = console.input("\n[user]user[/user] > ")
            if user_input.lower() in ['exit', 'quit']:
                console.print("[warning]Goodbye![/warning]")
                break
            if not user_input.strip(): continue

            messages.append({"role": "user", "content": user_input})

            while True:
                prompt = "".join([f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages])
                prompt += "<|im_start|>assistant\n"

                response_text = ""
                with Live(Spinner("dots", text="Jules is thinking...", style="cyan"), refresh_per_second=10, console=console, transient=True) as live:
                    try:
                        job = client.submit(prompt, api_name="/predict")
                        for text_chunk in job:
                            if isinstance(text_chunk, str):
                                response_text = text_chunk
                                # Only render markdown if it doesn't look like a tool call is starting
                                if "<tool>" not in response_text:
                                    live.update(Markdown(response_text))
                                else:
                                    live.update(Text(response_text))
                    except Exception as e:
                        live.update(f"[danger]Error during inference: {e}[/danger]")
                        break

                if "<tool>" in response_text:
                    try:
                        parts = response_text.split("<tool>")
                        # Print pre-tool text if any
                        if parts[0].strip():
                            console.print(Markdown(parts[0].strip()))

                        tool_str = parts[1].split("</tool>")[0].strip()
                        tool_data = json.loads(tool_str)
                        name = tool_data.get("name")
                        args = tool_data.get("args", {})

                        if name == "read_file": result = read_file(**args)
                        elif name == "write_file": result = write_file(**args)
                        elif name == "execute_command": result = execute_command(**args)
                        else: result = "Tool not found."

                        messages.append({"role": "assistant", "content": response_text})
                        messages.append({"role": "user", "content": f"Tool execution result:\n{result}"})
                    except Exception as e:
                        console.print(f"[danger]Failed to parse tool JSON: {e}[/danger]")
                        messages.append({"role": "assistant", "content": response_text})
                        messages.append({"role": "user", "content": f"Failed to parse tool JSON: {e}"})
                else:
                    # Final response (pure text)
                    console.print(Markdown(response_text))
                    messages.append({"role": "assistant", "content": response_text})
                    break

        except KeyboardInterrupt:
            console.print("\n[warning]Session interrupted.[/warning]")
            break

def main():
    chat_loop()

if __name__ == "__main__":
    main()
