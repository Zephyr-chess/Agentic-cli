# Agentic CLI

A high-polish, lightweight AI coding assistant for Android Termux, powered by OpenRouter.

## Features
- **Ultra-Lightweight**: Only depends on `rich` and `requests`. No heavy UI frameworks.
- **Auto-Pilot Mode**: The agent can plan and execute tasks fully autonomously.
- **Modern Web Dashboard**: A professional streaming interface launched with `--web`.
- **Interactive Setup**: Easy API key and model management via `/setup`.
- **Ultra-Lightweight**: Zero-cost inference and minimal dependency footprint.
- **Optimized for Termux**: Built specifically for mobile developer workflows.

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

3. Launch the assistant (Terminal):
   ```bash
   agentic-cli
   ```

4. Launch the assistant (Browser):
   ```bash
   agentic-cli --web
   ```
   *On the first run, you will be prompted for your OpenRouter API Key.*

## Configuration
Settings are stored in `~/.agentic_cli_config.json`.
Default model: `qwen/qwen3-coder:free` (480B MoE).
