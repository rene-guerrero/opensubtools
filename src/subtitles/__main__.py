#!/usr/bin/env python3
"""Main entry point for subtitles package.

Usage:
  python -m subtitles sync <srt_file> <offset_ms>
  python -m subtitles translate <srt_file>
  python -m subtitles generate <video_file>
  python -m subtitles batch <folder>
  python -m subtitles extract <folder>
"""

import argparse
import sys

from subtitles import __version__


def main():
    """Main CLI dispatcher."""
    parser = argparse.ArgumentParser(
        description="Subtitle extraction, translation, and synchronization toolkit",
        prog="subtitles"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Sync command
    sync_parser = subparsers.add_parser(
        "sync",
        help="Synchronize subtitle timing"
    )
    sync_parser.add_argument("path", help="Path to .srt file")
    sync_parser.add_argument("offset_ms", type=int, help="Offset in milliseconds")
    sync_parser.add_argument("--config", default=None, help="Config file path")
    
    # Translate command
    translate_parser = subparsers.add_parser(
        "translate",
        help="Translate subtitles from English to Spanish"
    )
    translate_parser.add_argument("path", help="Path to .srt file")
    translate_parser.add_argument("--config", default=None, help="Config file path")
    translate_parser.add_argument("-o", "--output", default=None, help="Output file path")
    
    # Generate command
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate subtitles for a video"
    )
    generate_parser.add_argument("path", help="Path to video file")
    generate_parser.add_argument("--config", default=None, help="Config file path")
    
    # Batch command
    batch_parser = subparsers.add_parser(
        "batch",
        help="Batch process all videos in a folder"
    )
    batch_parser.add_argument("folder", help="Path to folder")
    batch_parser.add_argument("--config", default=None, help="Config file path")
    
    # Extract command
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract embedded subtitles from videos"
    )
    extract_parser.add_argument("folder", help="Path to folder")
    extract_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing")
    extract_parser.add_argument("--config", default=None, help="Config file path")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Dispatch to appropriate CLI module
    if args.command == "sync":
        from subtitles.cli.sync import main as sync_main
        sys.argv = ["subtitles", "sync", args.path, str(args.offset_ms)]
        if args.config:
            sys.argv.extend(["--config", args.config])
        sync_main()
    elif args.command == "translate":
        from subtitles.cli.translate import main as translate_main
        sys.argv = ["subtitles", "translate", args.path]
        if args.config:
            sys.argv.extend(["--config", args.config])
        if args.output:
            sys.argv.extend(["-o", args.output])
        translate_main()
    elif args.command == "generate":
        from subtitles.cli.generate import main as generate_main
        sys.argv = ["subtitles", "generate", args.path]
        if args.config:
            sys.argv.extend(["--config", args.config])
        generate_main()
    elif args.command == "batch":
        from subtitles.cli.batch import main as batch_main
        sys.argv = ["subtitles", "batch", args.folder]
        if args.config:
            sys.argv.extend(["--config", args.config])
        batch_main()
    elif args.command == "extract":
        from subtitles.cli.extract import main as extract_main
        sys.argv = ["subtitles", "extract", args.folder]
        if args.config:
            sys.argv.extend(["--config", args.config])
        if args.overwrite:
            sys.argv.append("--overwrite")
        extract_main()


if __name__ == '__main__':
    main()
