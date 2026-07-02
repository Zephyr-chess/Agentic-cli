# Agentic CLI

A local AI coding assistant designed for Android Termux, with remote inference powered by Hugging Face Spaces.

## Features
- **Local Execution:** Runs shell commands and modifies files directly on your device.
- **Claude-style UI:** Beautiful terminal interface using `rich`.
- **Multi-Backend Support:** Switch between Hugging Face Space and OpenRouter.
- **Flexible Models:** Supports powerful models like Llama 3 70B via OpenRouter.
- **Optimized for Termux:** Tailored setup for Android environments.

## Architecture
- **Backends:**
  - Hugging Face Space running `llama-cpp-python` with Gradio (Default).
  - OpenRouter API for high-performance models.
- **Client:** Python CLI tool using `gradio_client` and `rich`.

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

## Configuration

### OpenRouter Setup
To use OpenRouter, set your API key:
```bash
export OPENROUTER_API_KEY=your_key_here
```
In the CLI, switch backends:
```text
/backend openrouter
/model meta-llama/llama-3.1-70b-instruct
```

### Hugging Face Setup
If you want to use a custom HF Space:
```bash
export HF_REPO_ID=your-username/your-space-name
```

## CLI Commands
- `/model <name>`: Change the OpenRouter model.
- `/backend <hf|openrouter>`: Switch between backends.
- `/status`: Show current configuration.
- `exit`: Quit the session.

## Backend Deployment (Hugging Face)

If you wish to host your own backend:
1. Create a new Hugging Face Space (Gradio SDK).
2. Upload the contents of the `backend/` directory.
3. Update `REPO_ID` in `agentic_cli/main.py` to point to your Space.

## Development

- `backend/`: Files for the Hugging Face Space.
- `agentic_cli/`: Local client source code.
- `setup.py`: Package configuration and entry points.
