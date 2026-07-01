#!/usr/bin/env node

const { spawn } = require('child_process');

const pythonProcess = spawn('python3', ['-m', 'agentic_cli.main'], {
    stdio: 'inherit',
    env: process.env
});

pythonProcess.on('close', (code) => {
    process.exit(code);
});
