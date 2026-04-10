---
name: model-training
description: >
  This skill is responsible for training machine learning models using provided datasets. 
  It includes the steps of dataset preparation, model training, evaluation, and packaging for local deployment or further use in the OpenClaw system. 
  The skill can handle tasks such as fine-tuning, hyperparameter optimization, and evaluating model performance.
  The skill also allows for **retraining** the model with new data that can be generated, such as the results from the `video_content_analysis` skill.
---

## How to Use

1. **Prepare the Dataset:**
   Before training, ensure the dataset is in the correct format (`train.jsonl`, `valid.jsonl`, `test.jsonl`). The dataset can be updated by appending new data, such as transcripts from videos processed by the **`video_content_analysis`** skill.

2. **Run the Training Script:**
   Use the provided script to train the model. The script handles fine-tuning using LoRA or full model training.

3. **Evaluate and Package the Model:**
   After training, evaluate the model performance. If the model passes the evaluation, it will be packaged into a format suitable for deployment with Ollama.

Run the training script as follows:

```bash
bash ~/.openclaw/workspace/skills/model_training/scripts/train_lora.sh
```

### Script Details

- prepare_dataset.py: Prepares the training dataset by cleaning and formatting it. It can handle new data from video_content_analysis by appending transcripts or other data into the training set.
- train_lora.sh: Runs the LoRA fine-tuning process on the selected model, using the updated dataset, which can include the new video transcript data.
- eval_model.sh: Evaluates the trained model's performance using a validation dataset. This helps determine if the newly trained model is performing as expected.
- package_ollama.sh: Packages the trained model for deployment with Ollama.

## Workflow

1. Prepare the dataset for training (ensure it's in train.jsonl, valid.jsonl, and test.jsonl format).
   - Video content analysis results are stored in skills/video_content_analysis/data/raw (txt files) and skills/video_content_analysis/data/summaries (md files). These files should be used to augment the training dataset.
2. Fine-tune the model using the provided script (train_lora.sh).
   - New data from video_content_analysis can be appended to the existing dataset to improve the model’s performance.
3. Evaluate the model using eval_model.sh.
   - After training, evaluate the model on the validation dataset to assess the accuracy and performance of the retrained model.
4. Package the model if evaluation is successful using package_ollama.sh.
   - Once the model passes evaluation, it will be packaged for deployment with Ollama for use in other agents like fin_analyst.
