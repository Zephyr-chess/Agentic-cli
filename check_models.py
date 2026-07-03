import requests

response = requests.get("https://openrouter.ai/api/v1/models")
models = response.json().get('data', [])
qwen_models = [m['id'] for m in models if 'qwen' in m['id'].lower() and 'free' in m['id'].lower()]
for m in qwen_models:
    print(m)
