# Agentic CLI

A high-polish, lightweight AI coding assistant for Android Termux, powered by OpenRouter.

## Features
- **Ultra-Lightweight**: Only depends on `rich` and `requests`. No heavy UI frameworks.
- **Autonomous Workflow**: The agent can plan and execute multiple tasks in sequence.
- **Interactive TUI-feel**: Uses `rich` for a modern, colorful terminal experience with Markdown support.
- **Browser-Based UI**: A modern web interface (inspired by OpenCode/Claude Code) for a GUI chat experience.
- **Optimized for Termux**: Fast installation and minimal CPU/RAM usage.

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
