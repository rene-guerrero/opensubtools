"""Batch tab - Batch process videos."""
import customtkinter as ctk
from pathlib import Path
from threading import Thread
import sys
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from subtitles.gui.widgets import FolderDropTarget, LanguageSelector


class TextboxLogHandler(logging.Handler):
    """Custom log handler that writes to a CTkTextbox."""

    def __init__(self, textbox):
        super().__init__()
        self.textbox = textbox
        self.formatter = logging.Formatter('%(levelname)s: %(message)s')

    def emit(self, record):
        msg = self.formatter.format(record)
        self.textbox.after(0, lambda m=msg: self._append_log(m))

    def _append_log(self, msg):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", msg + "\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")


class BatchTab:
    """Batch processing tab."""

    def __init__(self, parent):
        self.parent = parent
        self.selected_folder = None
        self.create_widgets()
        self.setup_logging()

    def create_widgets(self):
        """Create tab widgets."""
        # Title
        title = ctk.CTkLabel(
            self.parent,
            text="Batch generate subtitles",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        title.pack(pady=(0, 15))

        # Drop zone for folder
        self.drop_zone = FolderDropTarget(
            self.parent,
            on_drop=self.on_folder_dropped
        )
        self.drop_zone.pack(fill="x", pady=10)

        # Selected folder label
        self.folder_label = ctk.CTkLabel(
            self.parent,
            text="No folder selected",
            text_color="gray",
            anchor="w"
        )
        self.folder_label.pack(pady=5, fill="x", padx=10)

        # Language selector and Process button in same row
        controls_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        controls_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(controls_frame, text="Language:").pack(side="left")

        self.lang_selector = LanguageSelector(controls_frame)
        self.lang_selector.pack(side="left", padx=10)

        # Process button
        self.process_btn = ctk.CTkButton(
            controls_frame,
            text="Process",
            command=self.start_batch,
            state="disabled",
            fg_color="#2FA572",
            hover_color="#247559",
            width=100
        )
        self.process_btn.pack(side="right")

        # Progress
        self.progress = ctk.CTkProgressBar(self.parent, width=400)
        self.progress.pack(pady=5)
        self.progress.set(0)

        # Status (aligned left)
        self.status_label = ctk.CTkLabel(
            self.parent,
            text="",
            text_color="gray",
            anchor="w"
        )
        self.status_label.pack(pady=5, fill="x", padx=10)

        # Log output box
        log_frame = ctk.CTkFrame(self.parent)
        log_frame.pack(fill="both", expand=True, pady=10)

        ctk.CTkLabel(log_frame, text="Logs:").pack(anchor="w", padx=5, pady=(5, 0))

        self.log_textbox = ctk.CTkTextbox(
            log_frame,
            height=100,
            state="disabled",
            wrap="word"
        )
        self.log_textbox.pack(fill="both", expand=True, padx=5, pady=5)

    def setup_logging(self):
        """Setup logging to textbox."""
        handler = TextboxLogHandler(self.log_textbox)
        handler.setLevel(logging.INFO)
        logger = logging.getLogger()
        logger.addHandler(handler)

    def on_folder_dropped(self, folder_path: Path):
        """Handle folder drop."""
        self.selected_folder = folder_path
        self.folder_label.configure(
            text=f"Selected: {folder_path.name}",
            text_color="white"
        )
        self.process_btn.configure(state="normal")
        self.status_label.configure(text="")

    def start_batch(self):
        """Start batch processing."""
        if not self.selected_folder:
            return

        self.process_btn.configure(state="disabled")
        self.progress.set(0)

        thread = Thread(target=self.process_folder, daemon=True)
        thread.start()

    def process_folder(self):
        """Process folder in background."""
        try:
            from subtitles.core.extractor import extract_english_subtitles, extract_spanish_subtitles
            from subtitles.core.translator import translate_srt_file, find_and_translate_local_srt
            from subtitles.core.downloader import download_english_subtitle, download_spanish_subtitle
            from subtitles.utils.config import get_config

            config = get_config()
            target_lang = self.lang_selector.get_language()

            # Find all videos
            video_extensions = tuple(config.video_formats)
            video_files = []

            for ext in video_extensions:
                video_files.extend(self.selected_folder.rglob(f"*{ext}"))

            video_files = sorted(video_files)

            if not video_files:
                self.parent.after(0, lambda: self.status_label.configure(
                    text="No video files found",
                    text_color="#FF5555"
                ))
                return

            total = len(video_files)
            success = 0
            failed = 0
            skipped = 0

            for i, video in enumerate(video_files):
                self.parent.after(0, lambda: self.progress.set((i + 1) / total))
                self.parent.after(0, lambda: self.status_label.configure(
                    text=f"Processing {i + 1}/{total}: {video.name}"
                ))

                output_srt = video.parent / f"{video.stem}.srt"

                # Skip if already has subtitle in target language
                if output_srt.exists():
                    skipped += 1
                    continue

                # Try different methods
                method_success = False

                # 1. Local SRT
                if find_and_translate_local_srt(video, output_srt, target_lang=target_lang):
                    method_success = True

                # 2. Extract Spanish
                if not method_success:
                    temp_srt = video.parent / f"{video.stem}.temp.srt"
                    if extract_spanish_subtitles(video, temp_srt):
                        temp_srt.rename(output_srt)
                        method_success = True

                # 3. Extract & translate English
                if not method_success:
                    temp_srt = video.parent / f"{video.stem}.temp.srt"
                    char_count = extract_english_subtitles(video, temp_srt)
                    if char_count and char_count > 0:
                        if translate_srt_file(temp_srt, output_srt, target_lang=target_lang):
                            temp_srt.unlink(missing_ok=True)
                            method_success = True

                # 4. Download
                if not method_success:
                    downloaded = download_spanish_subtitle(video)
                    if downloaded:
                        downloaded.rename(output_srt)
                        method_success = True
                    else:
                        downloaded = download_english_subtitle(video)
                        if downloaded:
                            if translate_srt_file(downloaded, output_srt, target_lang=target_lang):
                                downloaded.unlink(missing_ok=True)
                                method_success = True

                if method_success:
                    success += 1
                else:
                    failed += 1

            # Final results
            self.parent.after(0, lambda: self.progress.set(1.0))
            self.parent.after(0, lambda: self.status_label.configure(
                text=f"Complete: {success} success, {failed} failed, {skipped} skipped",
                text_color="#2FA572"
            ))

        except Exception as e:
            self.parent.after(0, lambda: self.status_label.configure(
                text=f"Error: {str(e)}",
                text_color="#FF5555"
            ))
        finally:
            self.parent.after(0, lambda: self.process_btn.configure(state="normal"))
