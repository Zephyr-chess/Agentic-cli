import gradio as gr
from huggingface_hub import hf_hub_download
from llama_cpp import Llama

# Fetch the highly optimized 4-bit quantized developer model
model_path = hf_hub_download(
    repo_id="Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
    filename="qwen2.5-coder-3b-instruct-q4_k_m.gguf"
)

# Initialize Llama.cpp constrained to 2 vCPUs with a 4096 token context window
llm = Llama(model_path=model_path, n_ctx=4096, n_threads=2, verbose=False)

def generate(formatted_prompt):
    """
    Accepts a ChatML formatted string, streams token generation from
    Llama.cpp, and yields cumulative text chunks back to the Gradio client.
    """
    stream = llm(
        formatted_prompt,
        max_tokens=1024,
        stop=["<|im_end|>"],
        stream=True
    )
    text = ""
    for chunk in stream:
        text += chunk['choices'][0]['text']
        yield text

# Expose the execution stream via a lightweight Gradio interface
iface = gr.Interface(fn=generate, inputs="text", outputs="text")
iface.launch()
