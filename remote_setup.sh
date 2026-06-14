#!/bin/bash
# Remote Setup Script for 192.168.0.116 (RTX 3090)
# This script installs Ollama and pulls the best models for the Digitization Pipeline.

echo "🚀 Starting Local LLM/VLLM Setup on 192.168.0.116..."

# 1. Install Ollama (standard Linux install)
if ! command -v ollama &> /dev/null; then
    echo "📦 Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "✅ Ollama already installed."
fi

# 2. Start Ollama service (if not running)
if ! pgrep -x "ollama" > /dev/null; then
    echo "🏃 Starting Ollama service..."
    ollama serve &
    sleep 5
fi

# 3. Pull Best Models for 24GB VRAM
echo "📥 Pulling Llama 3 8B (Text-to-Schema)..."
ollama pull llama3:8b

echo "📥 Pulling LLaVA 13B (Vision-to-Schema)..."
ollama pull llava:13b

# 4. Pull a lightweight model for fast sanity checks
echo "📥 Pulling Phi-3 Mini..."
ollama pull phi3:mini

echo "✅ Remote machine is ready."
echo "--------------------------------------------------------"
echo "Ollama API is running at: http://192.168.0.116:11434"
echo "You can now use LocalOllamaProcessor or LocalVLLMProcessor."
echo "--------------------------------------------------------"
