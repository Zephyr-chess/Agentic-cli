import os
import json
import subprocess
import sys
import requests
import asyncio
import threading
from typing import List, Dict

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, DynamicContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.widgets import TextArea, Frame, Label
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import WordCompleter

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from rich.panel import Panel

# Constants
CONFIG_PATH = os.path.expanduser("~/.agentic_cli_config.json")
DEFAULT_MODEL = "qwen/qwen-2.5-coder-32b-instruct:free"

class AgentConfig:
    def __init__(self):
        self.load()

    def load(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    self.data = json.load(f)
            except:
                self.data = self.default_data()
        else:
            self.data = self.default_data()

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

# UI Styles
style = Style.from_dict({
    'status-bar': '#ffffff bg:#4444ff',
    'input-field': '#ffffff bg:#000000',
    'chat-area': '#cccccc bg:#000000',
    'title': '#ffff00 bold',
    'user': '#00ff00 bold',
    'assistant': '#00ffff bold',
    'tool': '#ff00ff bold',
})

class TUI:
    def __init__(self):
        self.chat_history = []
        self.messages = [{"role": "system", "content": "You are Jules, an expert senior software engineer and autonomous coding agent. You assist the user with reading, writing, and executing code locally. Use <tool>JSON</tool> format for actions."}]
        self.is_loading = False

        # UI Components
        self.output_field = TextArea(read_only=True, scrollbar=True, style='class:chat-area')
        self.input_field = TextArea(height=3, prompt='user > ', multiline=True, style='class:input-field')
        self.status_label = Label(text=self.get_status_text(), style='class:status-bar')

        # Layout
        self.root_container = HSplit([
            Window(height=1, content=FormattedTextControl([('class:title', ' Agentic CLI v1.5 | Ctrl+Q: Quit | Ctrl+S: Setup | Ctrl+L: Clear ')]), align='center'),
            Frame(self.output_field),
            self.status_label,
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
        return f" Backend: {config.backend} | Model: {config.current_model} | Status: {'Thinking...' if self.is_loading else 'Ready'}"

    def update_status(self):
        self.status_label.text = self.get_status_text()
        self.app.invalidate()

    def append_to_chat(self, role, text):
        role_style = 'user' if role == 'user' else 'assistant'
        self.output_field.text += f"\n[{role.upper()}]\n{text}\n"
        # Auto scroll to bottom
        self.output_field.buffer.cursor_position = len(self.output_field.text)

    def setup_keybindings(self):
        @self.kb.add('c-q')
        def exit_(event):
            event.app.exit()

        @self.kb.add('c-l')
        def clear_(event):
            self.output_field.text = ""
            self.messages = [self.messages[0]]
            self.app.invalidate()

        @self.kb.add('enter')
        def submit_(event):
            if not self.is_loading:
                text = self.input_field.text.strip()
                if text:
                    self.input_field.text = ""
                    self.append_to_chat("user", text)
                    self.messages.append({"role": "user", "content": text})
                    self.is_loading = True
                    self.update_status()
                    # Run inference in a separate thread
                    threading.Thread(target=self.run_inference, args=(list(self.messages),), daemon=True).start()

    def run_inference(self, messages):
        response_text = ""
        backend = config.backend
        key = config.data[backend]["key"]
        model = config.data[backend]["model"]

        if not key and backend != "hf":
            self.append_to_chat("system", "Error: API key not set. Use Ctrl+S to configure.")
            self.is_loading = False
            self.update_status()
            return

        try:
            # Simple synchronous request for now to maintain lightweight feel
            if backend in ["openrouter", "openai", "gemini"]:
                url = "https://openrouter.ai/api/v1/chat/completions" if backend == "openrouter" else \
                      "https://api.openai.com/v1/chat/completions" if backend == "openai" else \
                      "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload = {"model": model, "messages": messages, "stream": False}
                res = requests.post(url, headers=headers, json=payload)
                res.raise_for_status()
                response_text = res.json()['choices'][0]['message']['content']

            elif backend == "anthropic":
                headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
                payload = {"model": model, "messages": [m for m in messages if m['role'] != 'system'], "system": messages[0]['content'], "max_tokens": 4096}
                res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
                res.raise_for_status()
                response_text = res.json()['content'][0]['text']

            # Process response and tools
            self.append_to_chat("assistant", response_text)
            self.messages.append({"role": "assistant", "content": response_text})

            if "<tool>" in response_text:
                self.handle_tool(response_text)
            else:
                self.is_loading = False
                self.update_status()

        except Exception as e:
            self.append_to_chat("system", f"Error: {e}")
            self.is_loading = False
            self.update_status()

    def handle_tool(self, response_text):
        try:
            tool_str = response_text.split("<tool>")[1].split("</tool>")[0].strip()
            tool_data = json.loads(tool_str)
            name = tool_data.get("name")
            args = tool_data.get("args", {})

            result = ""
            if name == "read_file":
                with open(args['path'], 'r') as f: result = f.read()
            elif name == "write_file":
                with open(args['path'], 'w') as f: f.write(args['content']); result = "Success"
            elif name == "execute_command":
                res = subprocess.run(args['cmd'], shell=True, capture_output=True, text=True)
                result = f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}"

            self.append_to_chat("system", f"Tool {name} result: {result[:100]}...")
            self.messages.append({"role": "user", "content": f"Tool execution result:\n{result}"})
            # Re-run inference with tool result
            self.run_inference(list(self.messages))
        except Exception as e:
            self.append_to_chat("system", f"Tool Error: {e}")
            self.is_loading = False
            self.update_status()

    def run(self):
        self.app.run()

def main():
    tui = TUI()
    tui.run()

if __name__ == "__main__":
    main()
