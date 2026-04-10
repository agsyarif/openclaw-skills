#!/bin/bash

# Set output paths
OUTPUT_PATH="./data/runs"
MODEL_NAME="fin-analyst-local"
MODIFIED_MODEL_PATH="${OUTPUT_PATH}/final_model"

# Package the trained model for Ollama
echo "Packaging the model for Ollama..."

ollama create $MODEL_NAME -f $MODIFIED_MODEL_PATH

echo "Model packaged successfully for Ollama!"