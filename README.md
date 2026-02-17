# Subtitle Extractor and Translator

Python script to extract embedded subtitles from video files, translate them from English to Spanish, and save them as `.srt` files.

## Requirements

- Python 3.12+
- FFmpeg (must be installed and in PATH)

### Installing FFmpeg

**Windows:**
```bash
winget install Gyan.FFmpeg
```

**Mac:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

## Installation

1. Clone or download this repository
2. Create and activate virtual environment:
```bash
py -3.12 -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

```bash
python extract_and_translate.py <folder_path>
```

### Options

- `--overwrite`: Overwrite existing `.srt` files

### Example

```bash
python extract_and_translate.py "C:\Users\YourUser\Videos\MyMovies"
```

## Supported Formats

- .mp4
- .mkv
- .avi
- .mov
- .wmv
- .flv
- .webm
- .m4v

## Features

- ✅ Automatically detects embedded subtitles
- ✅ Extracts subtitles in SRT format
- ✅ Translates from English to Spanish using Google Translate
- ✅ Preserves original subtitle timing
- ✅ Processes multiple videos in batch
- ✅ Shows progress with progress bars
- ✅ Error handling and retry logic for translations

## Notes

- Translation is done using the free Google Translate API
- There may be rate limits for very large files
- Translated subtitles are saved with the same video name but with `.es.srt` extension
