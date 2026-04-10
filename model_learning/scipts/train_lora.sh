#!/bin/bash

# Set model and dataset paths
# "mistral:7b"
MODEL_NAME="llama3.2:3b"
DATA_PATH="./data/prepared"
OUTPUT_PATH="./data/runs"
BATCH_SIZE=1
NUM_LAYERS=4
ITERATIONS=600

# Load previous model if exists for retraining
if [ -f "$OUTPUT_PATH/final_model" ]; then
  echo "Loading previous model for retraining..."
  PREVIOUS_MODEL="$OUTPUT_PATH/final_model"
else
  echo "No previous model found, starting from scratch..."
  PREVIOUS_MODEL="$MODEL_NAME"
fi

# Run the training process with LoRA adapter
echo "Starting LoRA fine-tuning for $PREVIOUS_MODEL..."

mlx_lm.lora \
  --model $PREVIOUS_MODEL \
  --train \
  --data $DATA_PATH \
  --iters $ITERATIONS \
  --batch-size $BATCH_SIZE \
  --num-layers $NUM_LAYERS \
  --grad-checkpoint \
  --mask-prompt \
  --adapter-path $OUTPUT_PATH

echo "Training completed and model saved to $OUTPUT_PATH"