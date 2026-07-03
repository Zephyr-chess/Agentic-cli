import os
import json
import subprocess
import sys
import requests
import asyncio
from typing import List, Dict

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, DynamicContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.widgets import TextArea, Frame, Label
from prompt_toolkit.styles import Style

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from rich.panel import Panel

# Constants
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
    def backend(self): return self.data.get("backend", "openrouter")
    @backend.setter
    def backend(self, val): self.data["backend"] = val

    @property
    def current_model(self):
        return self.data[self.backend].get("model", "")

config = AgentConfig()
console = Console()

# UI Styles
style = Style.from_dict({
    'status-bar': '#ffffff bg:#4444ff',
    'input-field': '#ffffff bg:#000000',
    'chat-area': '#cccccc bg:#000000',
    'title': '#ffff00 bold',
})

class TUI:
    def __init__(self):
        self.messages = [{"role": "system", "content": "You are Jules, an expert software engineer. Help the user locally. Use <tool>JSON</tool> for actions."}]
        self.is_loading = False

        self.output_field = TextArea(read_only=True, scrollbar=True, style='class:chat-area')
        self.input_field = TextArea(height=3, prompt='user > ', multiline=True, style='class:input-field')

        # Dynamic status bar
        self.status_control = FormattedTextControl(self.get_status_text)
        self.status_window = Window(content=self.status_control, height=1, style='class:status-bar')

        self.root_container = HSplit([
            Window(height=1, content=FormattedTextControl([('class:title', ' Agentic CLI | Ctrl+Q: Exit | Ctrl+P: Setup | Ctrl+L: Clear ')]), align='center'),
            Frame(self.output_field),
            self.status_window,
            self.input_field,
        ])

        self.kb = KeyBindings()
        self.setup_keybindings()

        self.app = Application(
            layout=Layout(self.root_container, focused_element=self.input_field),
            key_bindings=self.kb,
            style=style,
            full_screen=True,
        )

    def get_status_text(self):
        status = "Thinking..." if self.is_loading else "Ready"
        return f" Backend: {config.backend} | Model: {config.current_model} | Status: {status}"

    def append_to_chat(self, role, text):
        self.output_field.text += f"\n\n[{role.upper()}]\n{text}\n"
        self.output_field.buffer.cursor_position = len(self.output_field.text)

    def setup_keybindings(self):
        @self.kb.add('c-q')
        def _(event): event.app.exit()

        @self.kb.add('c-l')
        def _(event):
            self.output_field.text = ""
            self.messages = [self.messages[0]]

        @self.kb.add('c-s')
        @self.kb.add('c-p') # Added Ctrl+P as a fallback for setup
        def _(event):
            self.run_interactive_setup()

        @self.kb.add('enter')
        def _(event):
            if not self.is_loading:
                text = self.input_field.text.strip()
                if text:
                    self.input_field.text = ""
                    self.append_to_chat("user", text)
                    self.messages.append({"role": "user", "content": text})
                    self.is_loading = True
                    asyncio.create_task(self.run_inference())

    def run_interactive_setup(self):
        from questionary import select, text, password
        def _setup():
            choice = select("Setup Menu", choices=["Switch Backend", "Set API Key", "Change Model", "Use Nemotron Free", "Back"]).ask()
            if choice == "Switch Backend":
                config.backend = select("Backend:", choices=["openrouter", "openai", "anthropic", "gemini"]).ask()
            elif choice == "Set API Key":
                p = select("Provider:", choices=["openrouter", "openai", "anthropic", "gemini"]).ask()
                k = password(f"Key for {p}:").ask()
                if k: config.data[p]["key"] = k
            elif choice == "Change Model":
                p = select("Provider:", choices=["openrouter", "openai", "anthropic", "gemini"]).ask()
                m = text("Model:", default=config.data[p]["model"]).ask()
                if m: config.data[p]["model"] = m
            elif choice == "Use Nemotron Free":
                config.backend = "openrouter"
                config.data["openrouter"]["model"] = NEMOTRON_MODEL
                console.print(f"[green]Set to {NEMOTRON_MODEL}[/green]")

            config.save()

        self.app.suspend_to_terminal(_setup)

    async def run_inference(self):
        backend = config.backend
        key = config.data[backend]["key"]
        model = config.data[backend]["model"]

        if not key:
            self.append_to_chat("system", "Error: Key not set. Press Ctrl+P (or Ctrl+S).")
            self.is_loading = False
            return

        try:
            loop = asyncio.get_event_loop()
            if backend in ["openrouter", "openai", "gemini"]:
                url = "https://openrouter.ai/api/v1/chat/completions" if backend == "openrouter" else \
                      "https://api.openai.com/v1/chat/completions" if backend == "openai" else \
                      "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload = {"model": model, "messages": self.messages, "stream": False}

                res = await loop.run_in_executor(None, lambda: requests.post(url, headers=headers, json=payload))
                res.raise_for_status()
                response_text = res.json()['choices'][0]['message']['content']

            elif backend == "anthropic":
                headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
                payload = {"model": model, "messages": [m for m in self.messages if m['role'] != 'system'], "system": self.messages[0]['content'], "max_tokens": 4096}
                res = await loop.run_in_executor(None, lambda: requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload))
                res.raise_for_status()
                response_text = res.json()['content'][0]['text']

            self.append_to_chat("assistant", response_text)
            self.messages.append({"role": "assistant", "content": response_text})

            if "<tool>" in response_text:
                await self.handle_tool(response_text)
            else:
                self.is_loading = False

        except Exception as e:
            self.append_to_chat("system", f"Error: {e}")
            self.is_loading = False

    async def handle_tool(self, response_text):
        try:
            tool_str = response_text.split("<tool>")[1].split("</tool>")[0].strip()
            tool_data = json.loads(tool_str)
            name, args = tool_data.get("name"), tool_data.get("args", {})

            result = ""
            loop = asyncio.get_event_loop()
            if name == "read_file":
                result = await loop.run_in_executor(None, lambda: open(args['path'], 'r').read())
            elif name == "write_file":
                await loop.run_in_executor(None, lambda: open(args['path'], 'w').write(args['content']))
                result = "Success"
            elif name == "execute_command":
                res = await loop.run_in_executor(None, lambda: subprocess.run(args['cmd'], shell=True, capture_output=True, text=True))
                result = f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}"

            self.append_to_chat("system", f"Tool {name} result: {result[:50]}...")
            self.messages.append({"role": "user", "content": f"Tool execution result:\n{result}"})
            await self.run_inference()
        except Exception as e:
            self.append_to_chat("system", f"Tool Error: {e}")
            self.is_loading = False

async def main_async():
    tui = TUI()
    await tui.app.run_async()

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
