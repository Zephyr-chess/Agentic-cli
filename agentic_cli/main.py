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

    while True:
        try:
            current_info = f"({config.backend}:{config.current_model})"
            user_input = console.input(f"\n[user]user {current_info}[/user] > ")

            if not user_input.strip(): continue
            if user_input.lower() in ['exit', 'quit']: break

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
