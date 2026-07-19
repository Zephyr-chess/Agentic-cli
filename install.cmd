@echo off
echo 🚀 Initializing OpenCLI Setup for Windows...

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found. Please install Python from python.org.
    exit /b 1
)

:: Check for uv
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 📦 Installing uv via pip...
    pip install uv
)

:: Install as global tool
echo 🐍 Installing Agentic CLI with uv...
uv tool install . --force

echo ✅ Setup complete!
echo 🚀 Terminal UI: type 'agentic-cli'
echo 🌐 Browser UI: type 'agentic-cli --web'
echo 💡 Alternatively: uvx --from . agentic-cli
