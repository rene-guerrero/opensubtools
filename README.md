# Subtitle Tools

A comprehensive Python toolkit for extracting, translating, synchronizing, and managing subtitles from video files.

## Features

- **Extract**: Extract embedded subtitles from video files (MP4, MKV, AVI, etc.)
- **Translate**: Translate subtitles from English to Spanish with smart batching
- **Synchronize**: Adjust subtitle timing with millisecond precision
- **Download**: Download subtitles from online sources
- **Batch Processing**: Process entire folders recursively
- **GUI Application**: Modern desktop application with intuitive interface for all features

## Installation

### Prerequisites

- Python 3.12+
- FFmpeg (must be installed and in PATH)

#### Installing FFmpeg

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

### Package Installation

1. Clone or download this repository
2. Create and activate virtual environment:
```bash
py -3.12 -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

3. Install the package in development mode:
```bash
pip install -e .
```

Or install dependencies directly:
```bash
pip install -r requirements.txt
```

## Project Structure

```
subtitles/
├── src/
│   └── subtitles/
│       ├── __init__.py           # Package initialization
│       ├── __main__.py           # CLI entry point
│       ├── cli/                  # CLI commands
│       │   ├── sync.py          # Synchronize subtitles
│       │   ├── translate.py     # Translate subtitles
│       │   ├── generate.py      # Generate subtitles for video
│       │   ├── batch.py         # Batch process folders
│       │   └── extract.py       # Extract embedded subtitles
│       ├── core/                 # Business logic
│       │   ├── extractor.py     # Subtitle extraction
│       │   ├── translator.py    # Translation engine
│       │   ├── synchronizer.py  # Time synchronization
│       │   └── downloader.py    # Subtitle download
│       ├── gui/                  # GUI Application
│       │   ├── app.py           # Main application window
│       │   ├── widgets.py       # Custom widgets
│       │   └── tabs/            # GUI tabs for each feature
│       │       ├── generate.py  # Generate subtitles tab
│       │       ├── translate.py # Translate subtitles tab
│       │       ├── sync.py      # Synchronize subtitles tab
│       │       └── batch.py     # Batch processing tab
│       ├── utils/                # Utilities
│       │   ├── config.py        # Configuration management
│       │   ├── logging_config.py # Logging setup
│       │   ├── translate.py     # Translation utilities
│       │   └── subtitle.py      # SRT utilities
│       └── scripts/              # Utility scripts
│           └── generate_context_menu.py  # Windows context menu integration
├── README.md
└── requirements.txt
```

## Usage

### Using the Package

After installation, you can use the package as a module:

```bash
# Synchronize subtitles (move forward 3 seconds)
python -m subtitles sync "video.srt" 3000

# Translate subtitles from English to Spanish
python -m subtitles translate "video.srt"

# Generate subtitles for a video
python -m subtitles generate "video.mp4"

# Batch process all videos in a folder
python -m subtitles batch "C:\Users\YourUser\Videos"

# Extract embedded subtitles from videos
python -m subtitles extract "C:\Users\YourUser\Videos"
```

### Using Individual Scripts

You can also run individual CLI scripts directly:

```bash
# From the src directory
python -m subtitles.cli.sync "video.srt" 3000
python -m subtitles.cli.translate "video.srt"
python -m subtitles.cli.generate "video.mp4"
python -m subtitles.cli.batch "C:\Users\YourUser\Videos"
python -m subtitles.cli.extract "C:\Users\YourUser\Videos"
```

### GUI Application

Launch the modern desktop application with an intuitive graphical interface:

```bash
python -m subtitles.gui.app
```

**Interface Features:**
- **Easy File Selection**: Click buttons to browse and select files or folders
- **Dark Theme**: Modern dark mode interface for comfortable viewing
- **Real-time Progress**: Progress bars and status messages for all operations
- **Intuitive Design**: Clean tabbed interface organized by feature

The GUI provides four main features accessible through tabs:

#### Generate Tab
- **Select video file**: Click to browse and select a video file (supports MP4, MKV, AVI, MOV, WMV, FLV, WebM, M4V, MPG, MPEG)
- **Choose target language**: Select from 15+ languages for translation
- **Generate**: The application will:
  1. Look for existing local SRT files
  2. Extract Spanish subtitles if available
  3. Extract and translate English subtitles
  4. Download subtitles from online sources as fallback
- **Progress tracking**: Real-time progress bar and status updates

#### Translate Tab
- **Select SRT file**: Choose a subtitle file to translate
- **Choose target language**: Select destination language
- **Translate**: Converts subtitles to the selected language with smart batching
- **Output**: Creates a new file with language code (e.g., `video.es.srt`)

#### Sync Tab
- **Select SRT file**: Choose subtitle file to synchronize
- **Adjust timing**: Use the slider for precise millisecond adjustments
- **Quick presets**: One-click buttons for common adjustments (-5s, -1s, +1s, +5s)
- **Apply**: Creates a synchronized copy (e.g., `video.synced.srt`)

#### Batch Tab
- **Select folder**: Choose a directory to process
- **Recursive processing**: Automatically processes all videos in subfolders
- **Language selection**: Choose target language for translation
- **Bulk operations**: Process multiple videos simultaneously with progress tracking
- **Results summary**: View success/failure statistics

### Windows Context Menu Integration

You can add "Generate Subtitles" to the Windows right-click context menu for video files:

```bash
# Generate the .reg file
python src/subtitles/scripts/generate_context_menu.py

# Then double-click the generated video_context_menu.reg file
# Or run as administrator to apply automatically
```

After installation, right-click on any video file to see "Generate Subtitles" in the context menu.

### Configuration

Create a `config.yaml` file in your working directory to customize behavior:

```yaml
video:
  formats:
    - mp4
    - mkv
    - avi
    - mov
    - wmv

translation:
  max_batch_characters: 5000
  batch_size_subtitles: 50
  source_language: "en"
  target_language: "es"
  parallel_workers: 2

detection:
  english_keywords:
    - " the "
    - " and "
    - " to "

output:
  use_emoji: true
  verbose: false
```

## Supported Formats

### Video Formats
- .mp4
- .mkv
- .avi
- .mov
- .wmv
- .flv
- .webm
- .m4v
- .mpg
- .mpeg

### Subtitle Formats
- .srt (SubRip)
- Embedded subtitles (extracted via FFmpeg)

## How It Works

### Subtitle Generation (`generate`)

The generate command attempts multiple methods in order:

1. **Find local SRT**: Looks for a `.srt` file with the same name as the video
2. **Extract Spanish**: Extracts Spanish subtitles embedded in the video
3. **Extract & Translate**: Extracts English subtitles and translates them
4. **Download Spanish**: Downloads Spanish subtitles from online sources
5. **Download & Translate**: Downloads English subtitles and translates them

### Translation

The translation engine uses:
- Smart English detection with multiple heuristics
- Batch translation with Google Translate API
- Parallel processing for faster translations
- Formatting preservation (HTML/SSA tags)
- Fallback to individual line translation if batch fails

### Synchronization

Adjust subtitle timing by offset in milliseconds:
- Positive values: Move subtitles forward (later)
- Negative values: Move subtitles backward (earlier)

## Requirements

```
ffmpeg-python>=0.2.0
srt>=3.5.0
deep-translator>=1.11.0
pyyaml>=6.0
customtkinter>=5.2.1
```

## Troubleshooting

### FFmpeg not found
Make sure FFmpeg is installed and in your PATH:
```bash
ffmpeg -version
```

### Permission errors on Windows
Run your terminal as Administrator if you encounter permission issues.

### Translation rate limits
The free Google Translate API may have rate limits. The tool includes retry logic with exponential backoff.

## License

MIT License - Feel free to use and modify as needed.

## Contributing

Pull requests are welcome! Please ensure:
- Code follows the existing style
- All CLI scripts maintain backward compatibility
- New features include appropriate tests

## Author

Your Name

## Acknowledgments

- [FFmpeg](https://ffmpeg.org/) for video/subtitle processing
- [deep-translator](https://github.com/nidhaloff/deep-translator) for translation API
- [srt](https://github.com/cdown/srt) for SRT parsing
