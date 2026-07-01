# Agentic CLI

A local AI coding assistant designed for Android Termux, with remote inference powered by Hugging Face Spaces.

## Features
- **Local Execution:** Runs shell commands and modifies files directly on your device.
- **Claude-style UI:** Beautiful terminal interface using `rich`.
- **Zero-Cost Inference:** Uses Qwen 2.5 Coder 3B Instruct on Hugging Face Free Tier.
- **Optimized for Termux:** Tailored setup for Android environments.

## Architecture
- **Backend:** Hugging Face Space running `llama-cpp-python` with Gradio.
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

## Backend Deployment (Hugging Face)

If you wish to host your own backend:
1. Create a new Hugging Face Space (Gradio SDK).
2. Upload the contents of the `backend/` directory.
3. Update `REPO_ID` in `agentic_cli/main.py` to point to your Space.

## Development

- `backend/`: Files for the Hugging Face Space.
- `agentic_cli/`: Local client source code.
- `setup.py`: Package configuration and entry points.
