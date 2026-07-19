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
from agentic_cli.engine import AgentEngine, config

# Theme & Console
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "yellow",
    "danger": "bold red",
    "user": "bold green",
    "assistant": "bold blue",
    "tool": "bold yellow",
})
console = Console(theme=custom_theme)

def interactive_setup():
    from rich.prompt import Prompt
    while True:
        console.clear()
        console.print(Panel(Text("CONFIGURATION", style="bold white", justify="center"), border_style="white"))

        table = Table(show_header=True, header_style="bold white", expand=True, border_style="dim")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("1. Backend", config.backend)
        table.add_row("2. Model", config.current_model)
        table.add_row("3. Auto-Approve", "[green]Enabled[/green]" if config.auto_approve else "[red]Disabled[/red]")
        table.add_row("4. API Keys", "Manage keys...")
        table.add_row("5. Zen Models", "Quick switch to Zen")
        table.add_row("6. Launch Web UI", "http://localhost:5000")
        table.add_row("0. Exit Setup", "")

        console.print(table)
        choice = Prompt.ask("Selection", choices=["1", "2", "3", "4", "5", "6", "0"], default="0")

        if choice == "1":
            config.backend = Prompt.ask("Provider", choices=["openrouter", "openai", "anthropic", "gemini", "opencode_zen", "nvidia_nim"], default=config.backend)
        elif choice == "2":
            config.data[config.backend]["model"] = Prompt.ask("Model ID", default=config.current_model)
        elif choice == "3":
            config.auto_approve = not config.auto_approve
        elif choice == "4":
            p = Prompt.ask("Select Provider", choices=["openrouter", "openai", "anthropic", "gemini", "opencode_zen", "nvidia_nim"])
            k = Prompt.ask(f"Enter {p.upper()} Key", password=True)
            if k: config.data[p]["key"] = k
        elif choice == "5":
            zen_model = Prompt.ask("Select Zen Model", choices=["big-pickle", "mimo-v2-pro-free", "minimax-m2.5-free", "nemotron-3-super-free"], default="big-pickle")
            config.backend = "opencode_zen"
            config.data["opencode_zen"]["model"] = zen_model
            console.print(f"[green]Switched to Zen: {zen_model}[/green]")
            time.sleep(1)
        elif choice == "6":
            from agentic_cli.web.server import run_web_ui
            run_web_ui()
        elif choice == "0":
            break
        config.save()

def get_model_completer():
    from prompt_toolkit.completion import WordCompleter
    # Default set of popular models for autocomplete
    models = [
        "qwen/qwen3-coder:free",
        "qwen/qwen-2.5-coder-32b-instruct:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4o",
        "google/gemini-pro-1.5",
        "/setup", "/auto", "/manual", "/clear", "/help", "exit"
    ]
    return WordCompleter(models, ignore_case=True)

def chat_loop(auto_pilot=False):
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.styles import Style as PTStyle

    engine = AgentEngine()
    history = InMemoryHistory()
    completer = get_model_completer()

    pt_style = PTStyle.from_dict({
        'prompt': 'bold #ffffff',
        'arrow': 'bold #00ffff',
    })

    # Quick Check for current backend key
    if config.backend != "hf" and not config.data[config.backend]["key"]:
        console.print(f"[warning]No API key for {config.backend}. Use /setup to configure.[/warning]")

    console.clear()
    console.print(f"[dim]SYSTEM: {config.backend.upper()} | {config.current_model} | {'AUTO' if auto_pilot else 'MANUAL'}[/dim]\n")

    while True:
        try:
            # Use prompt_toolkit for autocomplete and history
            user_input = pt_prompt(
                [('class:prompt', 'grok '), ('class:arrow', '>>> ')],
                history=history,
                completer=completer,
                style=pt_style
            ).strip()

            if not user_input: continue
            if user_input.lower() in ['exit', 'quit']: break

            if user_input.startswith("/"):
                cmd = user_input.split()[0].lower()
                if cmd == "/setup": interactive_setup()
                elif cmd == "/auto": auto_pilot = True; console.print("[info]Auto-Pilot On[/info]")
                elif cmd == "/manual": auto_pilot = False; console.print("[info]Manual Mode On[/info]")
                elif cmd == "/clear": engine.messages = [engine.messages[0]]; console.clear(); console.print("[dim]Chat Reset[/dim]\n")
                elif cmd == "/help": console.print("[info]Commands: /setup, /auto, /manual, /clear, exit[/info]")
                else: console.print("[danger]Unknown command[/danger]")
                continue

            engine.messages.append({"role": "user", "content": user_input})

            while True:
                response_text = ""
                with Live(Spinner("dots", text=""), refresh_per_second=10, console=console, transient=True) as live:
                    for text_chunk in engine.get_completion():
                        response_text = text_chunk
                        if "<tool>" not in response_text:
                            if response_text.strip(): live.update(Markdown(response_text))
                        else:
                            live.update(Text("[executing...]"))

                if not response_text: break
                engine.messages.append({"role": "assistant", "content": response_text})

                if "<tool>" in response_text:
                    try:
                        parts = response_text.split("<tool>")
                        if parts[0].strip(): console.print(Markdown(parts[0].strip()))

                        tool_calls = response_text.split("<tool>")[1:]
                        tool_results = []

                        for call in tool_calls:
                            if "</tool>" not in call: continue
                            tool_str = call.split("</tool>")[0].strip()
                            tool_data = json.loads(tool_str)
                            name, args = tool_data.get("name"), tool_data.get("args", {})

                            if not auto_pilot and not config.auto_approve:
                                if console.input(f"\n[warning]Confirm {name}? [y/N] [/warning]").lower() != 'y':
                                    tool_results.append(f"Rejected: {name}")
                                    continue

                            res = engine.execute_tool(name, args)
                            tool_results.append(f"Output of {name}:\n{res}")

                        if tool_results:
                            engine.messages.append({"role": "user", "content": "\n\n".join(tool_results)})
                        else: break
                    except Exception as e:
                        console.print(f"[danger]Tool Error: {e}[/danger]")
                        break
                else:
                    console.print(Markdown(response_text))
                    break
        except KeyboardInterrupt: break

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", action="store_true")
    parser.add_argument("--auto", action="store_true")
    args, _ = parser.parse_known_args()

    if args.web:
        from agentic_cli.web.server import run_web_ui
        run_web_ui()
    else:
        chat_loop(auto_pilot=args.auto)

if __name__ == "__main__":
    main()
