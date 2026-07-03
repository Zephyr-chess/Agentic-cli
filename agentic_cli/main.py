import os
import json
import subprocess
import sys
import requests
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Button, Label, DataTable, Tree, ProgressBar, Markdown
from textual.binding import Binding
from textual.screen import Screen, ModalScreen
from textual.worker import worker
from textual import on, work

from rich.console import Console
from rich.markdown import Markdown as RichMarkdown
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax

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
            "openai": {"model": "gpt-4o", "key": ""},
            "anthropic": {"model": "claude-3-5-sonnet-20240620", "key": ""},
            "gemini": {"model": "gemini-1.5-pro", "key": ""},
        }

    def save(self):
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)

    @property
    def backend(self): return self.data.get("backend", "openrouter")

    @property
    def current_model(self):
        b = self.backend
        return self.data.get(b, {}).get("model", "")

config = AgentConfig()

# Widgets
class ToolCard(Static):
    def __init__(self, name: str, args: dict, **kwargs):
        super().__init__(**kwargs)
        self.tool_name = name
        self.args = args

    def render(self) -> Panel:
        return Panel(
            Text.assemble(
                ("Tool: ", "bold cyan"), (self.tool_name, "bold yellow"),
                ("\nArgs: ", "bold cyan"), (json.dumps(self.args, indent=2), "white")
            ),
            title="Action",
            border_style="blue"
        )

class ChatMessage(Static):
    def __init__(self, role: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content

    def render(self) -> Panel:
        color = "green" if self.role == "user" else "blue"
        return Panel(
            RichMarkdown(self.content),
            title=f"[bold]{self.role.upper()}[/bold]",
            border_style=color,
            padding=(1, 2)
        )

class ApprovalModal(ModalScreen[bool]):
    def __init__(self, action: str, details: str):
        super().__init__()
        self.action = action
        self.details = details

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"Approval Required: {self.action}", id="title")
            yield Static(self.details, id="details")
            with Horizontal(id="buttons"):
                yield Button("Approve", variant="success", id="approve")
                yield Button("Reject", variant="error", id="reject")

    @on(Button.Pressed, "#approve")
    def approve(self):
        self.dismiss(True)

    @on(Button.Pressed, "#reject")
    def reject(self):
        self.dismiss(False)

class AgenticApp(App):
    CSS = """
    Screen {
        background: $surface;
    }

    #main_container {
        height: 1fr;
    }

    #sidebar {
        width: 30;
        background: $panel;
        border-right: tall $primary;
        padding: 1;
    }

    #chat_area {
        width: 1fr;
        padding: 1;
    }

    #input_area {
        height: auto;
        border-top: tall $primary;
        padding: 1;
    }

    .log_entry {
        padding: 0 1;
        color: $text-muted;
        font-size: 80%;
    }

    #dialog {
        padding: 2;
        background: $surface;
        border: thick $primary;
        width: 60;
        height: auto;
        align: center middle;
    }

    #buttons {
        margin-top: 1;
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+s", "settings", "Settings"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main_container"):
            with Vertical(id="sidebar"):
                yield Label("Files", classes="title")
                yield Tree("./")
                yield Label("\nTask Timeline", classes="title")
                yield DataTable(id="timeline")
            with ScrollableContainer(id="chat_area"):
                yield Vertical(id="messages_list")
        with Vertical(id="input_area"):
            yield ProgressBar(id="progress", show_percentage=False, show_eta=False)
            yield Input(placeholder="Type a message or /command...", id="main_input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#timeline", DataTable).add_columns("Time", "Status", "Action")
        self.query_one("#progress").update(total=100, progress=0)
        self.messages = [{"role": "system", "content": "You are Jules, an expert software engineer. Help the user locally. Use <tool>JSON</tool> for actions."}]

    def get_status_text(self) -> str:
        return f"Model: {config.current_model} | Backend: {config.backend}"

    @on(Input.Submitted, "#main_input")
    async def handle_input(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text: return
        event.input.value = ""

        if text.startswith("/"):
            await self.handle_command(text)
            return

        self.add_message("user", text)
        self.messages.append({"role": "user", "content": text})
        self.run_inference()

    def add_message(self, role: str, content: str) -> None:
        self.query_one("#messages_list").mount(ChatMessage(role, content))
        self.call_after_refresh(self.scroll_to_bottom)

    def scroll_to_bottom(self) -> None:
        container = self.query_one("#chat_area")
        container.scroll_end(animate=False)

    @work(exclusive=True)
    async def run_inference(self) -> None:
        self.query_one("#progress").update(progress=10)
        backend = config.backend
        key = config.data.get(backend, {}).get("key", "")
        model = config.data.get(backend, {}).get("model", "")

        if not key:
            self.add_message("system", f"Error: API Key for {backend} not set.")
            return

        try:
            url = "https://openrouter.ai/api/v1/chat/completions" if backend == "openrouter" else \
                  "https://api.openai.com/v1/chat/completions" if backend == "openai" else \
                  "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {"model": model, "messages": self.messages, "stream": False}

            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: requests.post(url, headers=headers, json=payload, timeout=60)
            )
            response.raise_for_status()
            response_text = response.json()['choices'][0]['message']['content']

            self.query_one("#progress").update(progress=100)
            self.add_message("assistant", response_text)
            self.messages.append({"role": "assistant", "content": response_text})

            if "<tool>" in response_text:
                await self.process_tools(response_text)

        except Exception as e:
            self.add_message("system", f"Inference Error: {e}")
        finally:
            self.query_one("#progress").update(progress=0)

    async def process_tools(self, response_text: str) -> None:
        try:
            tool_calls = response_text.split("<tool>")[1:]
            for call in tool_calls:
                tool_str = call.split("</tool>")[0].strip()
                tool_data = json.loads(tool_str)
                name, args = tool_data.get("name"), tool_data.get("args", {})

                # Visual feedback
                self.query_one("#messages_list").mount(ToolCard(name, args))
                self.query_one("#timeline").add_row(datetime.now().strftime("%H:%M:%S"), "Wait", name)

                approved = True
                if not config.auto_approve:
                    approved = await self.push_screen_wait(ApprovalModal(name, json.dumps(args, indent=2)))

                if approved:
                    result = await self.execute_tool(name, args)
                    self.query_one("#timeline").add_row(datetime.now().strftime("%H:%M:%S"), "Done", name)
                    self.messages.append({"role": "user", "content": f"Tool Result for {name}: {result}"})
                    self.run_inference()
                else:
                    self.messages.append({"role": "user", "content": f"User rejected tool: {name}"})

        except Exception as e:
            self.add_message("system", f"Tool Processing Error: {e}")

    async def execute_tool(self, name: str, args: dict) -> str:
        try:
            if name == "read_file":
                with open(args['path'], 'r') as f: return f.read()
            elif name == "write_file":
                with open(args['path'], 'w') as f: f.write(args['content']); return "Success"
            elif name == "execute_command":
                res = subprocess.run(args['cmd'], shell=True, capture_output=True, text=True)
                return f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}"
            return "Unknown tool"
        except Exception as e:
            return f"Error: {e}"

    async def push_screen_wait(self, screen: ModalScreen[bool]) -> bool:
        return await self.push_screen(screen)

    async def handle_command(self, cmd: str) -> None:
        if cmd == "/clear":
            self.query_one("#messages_list").remove()
            self.query_one("#chat_area").mount(Vertical(id="messages_list"))
            self.messages = [self.messages[0]]
        elif cmd == "/status":
            self.add_message("system", self.get_status_text())

def main():
    app = AgenticApp()
    app.run()

if __name__ == "__main__":
    main()
