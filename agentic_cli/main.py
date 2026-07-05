import os
import json
import sys
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme
from agentic_cli.engine import AgentEngine, config

# CLI Theme
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "danger": "bold red",
    "user": "bold green",
    "assistant": "bold blue",
    "tool": "bold yellow",
})
console = Console(theme=custom_theme)

def interactive_setup():
    from rich.prompt import Prompt
    from rich.table import Table

    while True:
        console.clear()
        console.print(Panel(Text("Agentic CLI Settings", style="bold white", justify="center"), border_style="blue"))

        table = Table(show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Option", style="cyan", width=20)
        table.add_column("Value", style="green")

        table.add_row("1. Backend", config.backend)
        table.add_row("2. Model", config.current_model)
        table.add_row("3. OpenRouter Key", "***" if config.data["openrouter"]["key"] else "Not Set")
        table.add_row("4. Auto-Approve", str(config.auto_approve))
        table.add_row("5. Launch Web UI", "http://localhost:5000")
        table.add_row("0. Back to Chat", "")

        console.print(table)

        choice = Prompt.ask("\nChoose an option", choices=["1", "2", "3", "4", "5", "0"], default="0")

        if choice == "1":
            backend = Prompt.ask("Select backend", choices=["openrouter", "openai", "anthropic", "gemini"], default=config.backend)
            config.backend = backend
        elif choice == "2":
            model = Prompt.ask("Enter model name", default=config.current_model)
            config.data[config.backend]["model"] = model
        elif choice == "3":
            key = Prompt.ask("Enter OpenRouter API Key", password=True)
            if key: config.data["openrouter"]["key"] = key
        elif choice == "4":
            config.auto_approve = not config.auto_approve
            console.print(f"[info]Auto-Approve set to: {config.auto_approve}[/info]")
            time.sleep(1)
        elif choice == "5":
            from agentic_cli.web.server import run_web_ui
            run_web_ui()
        elif choice == "0":
            break

        config.save()

def chat_loop(auto_pilot=False):
    engine = AgentEngine()

    if not config.data["openrouter"]["key"]:
        console.print(Panel("Welcome! Please set your OpenRouter API Key.", style="blue"))
        key = input("OpenRouter Key > ").strip()
        if key:
            config.data["openrouter"]["key"] = key
            config.save()
        else: return

    console.print(Panel(Text(f"Agentic CLI | {config.current_model} | {'Auto-Pilot' if auto_pilot else 'Manual'}", style="bold white", justify="center"), border_style="blue"))
    console.print("[info]Commands: /setup, /auto, /manual, /clear, exit[/info]")

    while True:
        try:
            mode_str = "AUTO" if auto_pilot else "MANUAL"
            current_info = f"({config.backend}:{config.current_model} | {mode_str})"
            user_input = console.input(f"\n[user]user {current_info}[/user] > ")

            if not user_input.strip(): continue
            if user_input.lower() in ['exit', 'quit']: break

            if user_input.startswith("/"):
                cmd = user_input.split()[0].lower()
                if cmd == "/setup":
                    interactive_setup()
                elif cmd == "/auto":
                    auto_pilot = True
                    console.print("[info]Switched to Auto-Pilot mode.[/info]")
                elif cmd == "/manual":
                    auto_pilot = False
                    console.print("[info]Switched to Manual mode.[/info]")
                elif cmd == "/clear":
                    engine.messages = [{"role": "system", "content": engine.system_prompt}]
                    console.print("[info]Chat history cleared.[/info]")
                else:
                    console.print("[danger]Unknown command.[/danger]")
                continue

            engine.messages.append({"role": "user", "content": user_input})

            while True:
                response_text = ""
                with Live(Spinner("dots", text="Thinking...", style="cyan"), refresh_per_second=10, console=console, transient=True) as live:
                    for text_chunk in engine.get_completion():
                        response_text = text_chunk
                        if "<tool>" not in response_text: live.update(Markdown(response_text))
                        else: live.update(Text(response_text))

                if not response_text: break
                engine.messages.append({"role": "assistant", "content": response_text})

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

                            # Approval
                            if not auto_pilot and not config.auto_approve:
                                confirm = console.input(f"\n[warning]Approve {name}? [y/N][/warning] ")
                                if confirm.lower() != 'y':
                                    tool_results.append(f"Tool {name} rejected.")
                                    continue

                            res = engine.execute_tool(name, args)
                            tool_results.append(f"Result of {name}: {res}")
                        except Exception as e:
                            tool_results.append(f"Tool Error: {e}")

                    engine.messages.append({"role": "user", "content": "\n\n".join(tool_results)})
                else:
                    console.print(Markdown(response_text))
                    break
        except KeyboardInterrupt: break

def main():
    if "--web" in sys.argv:
        from agentic_cli.web.server import run_web_ui
        run_web_ui()
    else:
        auto = "--auto" in sys.argv
        chat_loop(auto_pilot=auto)

if __name__ == "__main__":
    main()
