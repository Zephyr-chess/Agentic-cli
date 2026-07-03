# Agentic CLI

A lightweight AI coding assistant for Android Termux, powered by OpenRouter.

## Features
- **Local Execution:** Runs shell commands and modifies files directly in Termux.
- **Claude-style UI:** Beautiful terminal interface using `rich`.
- **High Performance:** Defaults to Qwen 2 72B Instruct (Free) via OpenRouter.
- **Fast & Minimal:** No local LLM overhead, zero-cost inference.

## Installation (Termux)

1. Clone this repository:
   ```bash
   git clone <your-repo-url>
   cd agentic-cli
   ```

2. Run the installation script:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

3. Launch the assistant:
   ```bash
   agentic-cli
   ```
   *On the first run, you will be prompted for your OpenRouter API Key.*

## Configuration
Settings are stored in `~/.agentic_cli_config.json`. You can manually change the `model` there to any model supported by OpenRouter.
