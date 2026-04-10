#!/bin/bash

# Set paths for model and evaluation data
MODEL_PATH="./data/runs"
EVAL_DATA="./data/prepared/valid.jsonl"
OUTPUT_PATH="./data/runs/evaluation_results.txt"

# Run evaluation
echo "Evaluating the trained model..."

python3 ./scripts/evaluate_model.py --model_path $MODEL_PATH --eval_data $EVAL_DATA --output $OUTPUT_PATH

# Check if the evaluation was successful
if [ $? -eq 0 ]; then
  echo "Evaluation passed. Results saved to $OUTPUT_PATH"
else
  echo "Evaluation failed. Please check the logs."
  exit 1
fi