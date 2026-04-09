## How to Use

Run the provided bash script, passing the YouTube URL:

```bash
bash ~/.openclaw/workspace/skills/youtube-transcript-dlp/scripts/get_transcript.sh "<youtube_url>"
```

### Script Details

The script automatically downloads the latest standalone `yt-dlp` binary if it's not present in the scripts folder. It then uses `yt-dlp` to download the auto-generated or manual subtitles for the requested video and outputs the raw text to the console, cleaning up any subtitle formatting.
