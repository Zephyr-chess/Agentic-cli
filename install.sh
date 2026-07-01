#!/bin/bash
set -e

echo "🚀 Initializing Agentic CLI Setup for Termux..."

# Update and install system dependencies
echo "📦 Installing system dependencies..."
pkg update -y
pkg install -y clang rust python binutils git

# Set Android API Level for native compilation
export ANDROID_API_LEVEL=24

# Install the package in editable mode
echo "🐍 Installing Agentic CLI..."
pip install -e .

echo "✅ Setup complete! You can now run the assistant by typing: agentic-cli"
