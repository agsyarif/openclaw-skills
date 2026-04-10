import json
import os

# Paths to raw data
raw_data_path = "./skills/video_content_analysis/data/raw"
summaries_data_path = "./skills/video_content_analysis/data/summaries"
prepared_data_path = "./data/prepared"

# Function to append new data to the existing dataset
def append_video_data():
    # Load new transcript data (this can be the output from video_content_analysis)
    new_transcript = []
    for file_name in os.listdir(raw_data_path):
        if file_name.endswith(".txt"):
            with open(os.path.join(raw_data_path, file_name), "r") as file:
                text = file.read().strip()
                new_transcript.append({"prompt": text, "completion": "Expected output"})
    
    # Load existing train.jsonl to append new data
    with open(os.path.join(prepared_data_path, "train.jsonl"), "a") as f:
        for item in new_transcript:
            f.write(json.dumps(item) + "\n")
    
    # Optionally process the summaries as well (similar to transcripts)
    for file_name in os.listdir(summaries_data_path):
        if file_name.endswith(".md"):
            with open(os.path.join(summaries_data_path, file_name), "r") as file:
                summary = file.read().strip()
                new_transcript.append({"prompt": summary, "completion": "Summarized content"})
    
    # Save summaries if needed
    with open(os.path.join(prepared_data_path, "train.jsonl"), "a") as f:
        for item in new_transcript:
            f.write(json.dumps(item) + "\n")

    print("New data appended to train.jsonl.")

# Prepare the dataset
if __name__ == "__main__":
    append_video_data()

# -----------

# import json
# import os

# # Paths to raw data
# raw_data_path = "./data/raw"
# prepared_data_path = "./data/prepared"

# # Function to append new data to the existing dataset
# def append_data():
#     # Load the new transcript (this can be the output from video_content_analysis)
#     new_transcript = [{"prompt": "Text from video", "completion": "Expected output"}]  # Example new data
    
#     # Load existing train.jsonl to append new data
#     with open(os.path.join(prepared_data_path, "train.jsonl"), "a") as f:
#         for item in new_transcript:
#             f.write(json.dumps(item) + "\n")
    
#     print("New data appended to train.jsonl.")

# # Prepare the dataset
# if __name__ == "__main__":
#     append_data()