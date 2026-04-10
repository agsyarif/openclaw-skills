---
name: Video Content Analysis
description: >
This skill is responsible for extracting and processing video content from a YouTube URL.
It downloads the subtitles (auto-generated or manually uploaded), cleans them, and provides
the processed transcript for further use, such as training models or analysis.
This skill is ideal for any task that requires extracting useful information from videos,
including transcription and text cleaning for downstream tasks.
---

## How to Use

Run the provided bash script, passing the YouTube URL:

```bash
bash ~/.openclaw/workspace/skills/video_content_analysis/scripts/get_transcript.sh "<youtube_url>"
```

### Script Details

The script automatically downloads the latest standalone yt-dlp binary if it's not present in the scripts folder. It then uses yt-dlp to download the auto-generated or manual subtitles for the requested video and outputs the raw text to the console, cleaning up any subtitle formatting.

## Workflow

1. Accept a YouTube video URL as input.
2. Download subtitles using yt-dlp.
3. Clean up the VTT file by removing timestamps, tags, and unnecessary data.
4. Output the cleaned transcript into /data/raw/transcript.txt for further processing or training.
