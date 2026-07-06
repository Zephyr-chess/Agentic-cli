#!/bin/bash
set -e

echo "🚀 Initializing OpenCLI Setup..."

# Update and install system dependencies (Termux specific)
if command -v pkg &> /dev/null; then
    echo "📦 Installing system dependencies via pkg..."
    pkg update -y
    pkg install -y python git
fi

# uv is much faster for managing tools

# Install uv for faster dependency management if not present
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    pkg install -y uv
fi

# Install the package as a tool using uv
echo "🐍 Installing Agentic CLI with uv..."
uv tool install . --force

echo "✅ Setup complete!"
echo "🚀 Terminal UI: type 'agentic-cli'"
echo "🌐 Browser UI: type 'agentic-cli --web'"
echo "💡 Alternatively, you can run it without permanent installation using: uvx --from . agentic-cli"
