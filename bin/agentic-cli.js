#!/usr/bin/env node

const { spawn } = require('child_process');

const args = process.argv.slice(2);

const pythonProcess = spawn('python3', ['-m', 'agentic_cli.main', ...args], {
    stdio: 'inherit',
    env: process.env
});

pythonProcess.on('close', (code) => {
    process.exit(code);
});
