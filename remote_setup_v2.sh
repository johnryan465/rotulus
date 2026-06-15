#!/bin/bash
# Remote Setup Script for 192.168.0.116 (RTX 3090)
# Enforces external binding for the API.

echo "🚀 Starting Local LLM/VLLM Setup on 192.168.0.116..."

# 1. Install Ollama
if ! command -v ollama &> /dev/null; then
    echo "📦 Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

# 2. Stop existing if any and start with external binding
echo "🏃 Configuring Ollama for external access..."
pkill ollama
export OLLAMA_HOST=0.0.0.0:11434
ollama serve > /tmp/ollama.log 2>&1 &
sleep 10

# 3. Pull Models
echo "📥 Pulling models (this may take time)..."
ollama pull llama3:8b
ollama pull llava:13b

echo "✅ Remote machine is ready at http://192.168.0.116:11434"
