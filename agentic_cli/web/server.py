from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import json
import threading
from agentic_cli.main import AgentConfig, execute_tool, get_completion

app = Flask(__name__)
CORS(app)

config = AgentConfig()
chat_messages = [{"role": "system", "content": "You are Jules, an expert software engineer. Help the user locally. Use <tool>JSON</tool> for actions."}]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message')
    if not user_msg:
        return jsonify({"error": "No message"}), 400

    chat_messages.append({"role": "user", "content": user_msg})

    # We use a non-streaming completion for the web-ui simplicity for now
    # but we can enhance with SSE later
    response_text = ""
    for chunk in get_completion(chat_messages):
        response_text = chunk # Cumulate for simple JSON response

    chat_messages.append({"role": "assistant", "content": response_text})

    return jsonify({
        "response": response_text,
        "model": config.current_model
    })

@app.route('/approve', methods=['POST'])
def approve():
    # Placeholder for tool execution flow
    return jsonify({"status": "ok"})

def run_web_ui(port=5000):
    print(f"🚀 Launching Web UI at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
