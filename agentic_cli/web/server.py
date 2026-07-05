from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import os
import json
import threading
import time
from agentic_cli.engine import AgentEngine, config

import sys

# Ensure templates and static files are found when installed as a tool
if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'agentic_cli', 'web', 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'agentic_cli', 'web', 'static')
else:
    template_folder = os.path.join(os.path.dirname(__file__), 'templates')
    static_folder = os.path.join(os.path.dirname(__file__), 'static')

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
CORS(app)

# Global engine state for the web session
engine = AgentEngine()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/config', methods=['GET'])
def get_config():
    return jsonify({
        "backend": config.backend,
        "model": config.current_model,
        "auto_approve": config.auto_approve
    })

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message')
    is_auto = request.json.get('auto_pilot', False)
    if not user_msg: return jsonify({"error": "No message"}), 400

    engine.messages.append({"role": "user", "content": user_msg})

    def generate():
        while True:
            response_text = ""
            # Stream the agent's thoughts
            for chunk in engine.get_completion(stream=True):
                response_text = chunk
                yield f"data: {json.dumps({'type': 'thought', 'content': chunk})}\n\n"

            engine.messages.append({"role": "assistant", "content": response_text})

            if "<tool>" in response_text:
                tool_calls = response_text.split("<tool>")[1:]
                results = []
                for call in tool_calls:
                    try:
                        tool_str = call.split("</tool>")[0].strip()
                        tool_data = json.loads(tool_str)
                        name, args = tool_data.get("name"), tool_data.get("args", {})

                        # In web UI, if not auto, we might need a separate approval flow.
                        # For now, let's execute if auto_pilot or auto_approve is on.
                        if is_auto or config.auto_approve:
                            yield f"data: {json.dumps({'type': 'tool_start', 'name': name, 'args': args})}\n\n"
                            res = engine.execute_tool(name, args)
                            results.append(f"Result of {name}: {res}")
                            yield f"data: {json.dumps({'type': 'tool_end', 'name': name, 'result': res})}\n\n"
                        else:
                            # Pause and wait for manual approval (sent via a different endpoint)
                            yield f"data: {json.dumps({'type': 'approval_required', 'name': name, 'args': args})}\n\n"
                            return # Stop generator and wait for user action
                    except Exception as e:
                        results.append(f"Error: {e}")

                engine.messages.append({"role": "user", "content": "\n\n".join(results)})
                # Loop continues to next agent turn
            else:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/approve', methods=['POST'])
def approve():
    action = request.json.get('action') # 'approve' or 'reject'
    name = request.json.get('name')
    args = request.json.get('args')

    if action == 'approve':
        res = engine.execute_tool(name, args)
        engine.messages.append({"role": "user", "content": f"Tool Result for {name}: {res}"})
        # Note: In a real app we'd trigger the next inference turn here.
        # For simplicity, we'll return the result and let the UI trigger next.
        return jsonify({"status": "success", "result": res})
    else:
        engine.messages.append({"role": "user", "content": f"User rejected tool: {name}"})
        return jsonify({"status": "rejected"})

def run_web_ui(port=5000):
    print(f"🚀 Agentic CLI Web UI: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
