#!/bin/bash

# Check if URL is provided
if [ -z "$1" ]; then
  echo "Usage: bash get_transcript.sh <youtube_url>"
  exit 1
fi

URL="$1"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
YTDLP="$DIR/yt-dlp"

# Download yt-dlp if it doesn't exist
if [ ! -f "$YTDLP" ]; then
  echo "Downloading yt-dlp (first run only)..."
  curl -s -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o "$YTDLP"
  chmod +x "$YTDLP"
fi

# We use a temporary directory to store the downloaded vtt subtitle
TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"

# Download subtitle (try manual id, then auto id, then english)
# We use --skip-download to only get the subtitle
"$YTDLP" --skip-download --write-auto-sub --write-sub --sub-langs "id,en" --sub-format vtt "$URL" -o "transcript.%(ext)s" > /dev/null 2>&1

VTT_FILE=$(ls *.vtt 2>/dev/null | head -n 1)

if [ -z "$VTT_FILE" ]; then
  echo "Error: No transcript or subtitles found for this video."
else
  # Clean VTT file to plain text
  # 1. Remove WEBVTT header
  # 2. Remove timestamps (e.g. 00:00:00.000 --> 00:00:02.000)
  # 3. Remove styling tags like <c> or </c>
  # 4. Remove empty lines
  cat "$VTT_FILE" | grep -v "WEBVTT" | grep -v "Kind:" | grep -v "Language:" | grep -v "\-\->" | sed -E 's/<[^>]*>//g' | awk 'NF' | uniq
fi

# Cleanup
rm -rf "$TMP_DIR"