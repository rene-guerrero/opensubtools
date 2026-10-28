"""Generate tab - Generate subtitles for videos."""
import customtkinter as ctk
from pathlib import Path
from threading import Thread
import sys
import logging

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from subtitles.gui.widgets import FileDropTarget, LanguageSelector


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


class GenerateTab:
    """Generate subtitles tab."""

    def __init__(self, parent):
        self.parent = parent
        self.selected_file = None

        self.create_widgets()
        self.setup_logging()

    def create_widgets(self):
        """Create tab widgets."""
        # Title
        title = ctk.CTkLabel(
            self.parent,
            text="Extract, download or translate subtitles",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        title.pack(pady=(0, 15))

        # Drop zone
        self.drop_zone = FileDropTarget(
            self.parent,
            file_types=["mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "mpg", "mpeg"],
            on_drop=self.on_file_dropped
        )
        self.drop_zone.pack(fill="x", pady=10)

        # Selected file label
        self.file_label = ctk.CTkLabel(
            self.parent,
            text="No file selected",
            text_color="gray",
            anchor="w"
        )
        self.file_label.pack(pady=5, fill="x", padx=10)

        # Language selector and Generate button in same row
        controls_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        controls_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(controls_frame, text="Language:").pack(side="left")

        self.lang_selector = LanguageSelector(controls_frame)
        self.lang_selector.pack(side="left", padx=10)

        # Generate button
        self.generate_btn = ctk.CTkButton(
            controls_frame,
            text="Generate",
            command=self.start_generation,
            state="disabled",
            fg_color="#2FA572",
            hover_color="#247559",
            width=100
        )
        self.generate_btn.pack(side="right")

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

    def on_file_dropped(self, file_path: Path):
        """Handle file drop."""
        self.selected_file = file_path
        self.file_label.configure(
            text=f"Selected: {file_path.name}",
            text_color="white"
        )
        self.generate_btn.configure(state="normal")
        self.status_label.configure(text="")

    def start_generation(self):
        """Start subtitle generation in background thread."""
        if not self.selected_file:
            return

        self.generate_btn.configure(state="disabled")
        self.progress.set(0.1)
        self.status_label.configure(text="Processing...")

        thread = Thread(target=self.generate_subtitles, daemon=True)
        thread.start()

    def generate_subtitles(self):
        """Generate subtitles (runs in background)."""
        try:
            from subtitles.core.translator import find_and_translate_local_srt
            from subtitles.core.extractor import extract_english_subtitles, extract_subtitles_by_language
            from subtitles.core.downloader import download_subtitle
            from subtitles.core.translator import translate_srt_file
            from subtitles.utils.config import LANGUAGE_CODE_MAP

            video_path = self.selected_file
            target_lang = self.lang_selector.get_language()
            output_srt = video_path.parent / f"{video_path.stem}.srt"

            self.parent.after(0, lambda: self.progress.set(0.2))
            self.parent.after(0, lambda: self.status_label.configure(text="Checking for existing subtitles..."))

            success = False
            temp_srt = video_path.parent / f"{video_path.stem}.temp.srt"

            # 1. Find and translate local SRT file
            self.parent.after(0, lambda: self.progress.set(0.3))
            self.parent.after(0, lambda: self.status_label.configure(text="Looking for local .srt file..."))

            if find_and_translate_local_srt(video_path, output_srt, target_lang=target_lang):
                success = True

            # 2. Extract subtitles in target language from video
            if not success:
                self.parent.after(0, lambda: self.progress.set(0.4))
                status_msg = f"Extracting {target_lang} subtitles..."
                self.parent.after(0, lambda msg=status_msg: self.status_label.configure(text=msg))

                lang_codes = LANGUAGE_CODE_MAP.get(target_lang, [target_lang])

                if extract_subtitles_by_language(video_path, output_srt, lang_codes):
                    success = True

            # 3. Download subtitles in target language
            if not success:
                self.parent.after(0, lambda: self.progress.set(0.75))
                self.parent.after(0, lambda: self.status_label.configure(text=f"Downloading {target_lang} subtitles..."))

                downloaded = download_subtitle(video_path, target_lang)
                if downloaded:
                    self.parent.after(0, lambda: self.progress.set(1.0))
                    self.parent.after(0, lambda: self.status_label.configure(
                        text=f"Saved: {output_srt.name}",
                        text_color="#2FA572"
                    ))
                    success = True

            # 4. Extract English and translate to target language
            if not success:
                self.parent.after(0, lambda: self.progress.set(0.5))
                self.parent.after(0, lambda: self.status_label.configure(text="Extracting English subtitles..."))

                char_count = extract_english_subtitles(video_path, temp_srt)

                if char_count and char_count > 0:
                    self.parent.after(0, lambda: self.progress.set(0.65))
                    self.parent.after(0, lambda: self.status_label.configure(text=f"Translating to {target_lang}..."))

                    def update_progress(p):
                        mapped = 0.65 + (p * 0.3)
                        self.parent.after(0, lambda m=mapped: self.progress.set(m))

                    if translate_srt_file(temp_srt, output_srt, target_lang=target_lang, progress_callback=update_progress):
                        temp_srt.unlink(missing_ok=True)
                        success = True
                    else:
                        temp_srt.unlink(missing_ok=True)

            # 5. Download and translate if needed
            if not success:
                self.parent.after(0, lambda: self.progress.set(0.75))
                self.parent.after(0, lambda: self.status_label.configure(text="Downloading English subtitles..."))

                downloaded = download_subtitle(video_path, "en", use_temp=True)
                if downloaded:
                    self.parent.after(0, lambda: self.progress.set(0.85))
                    self.parent.after(0, lambda: self.status_label.configure(text=f"Translating to {target_lang}..."))

                    def update_progress(p):
                        mapped = 0.85 + (p * 0.1)
                        self.parent.after(0, lambda m=mapped: self.progress.set(m))

                    if translate_srt_file(downloaded, output_srt, target_lang=target_lang, progress_callback=update_progress):
                        # Clean up temp files
                        if downloaded.exists():
                            downloaded.unlink()
                        for temp_file in video_path.parent.glob(f"{video_path.stem}.temp.*.srt"):
                            temp_file.unlink(missing_ok=True)
                        success = True
                    else:
                        downloaded.unlink(missing_ok=True)

            self.parent.after(0, lambda: self.progress.set(1.0))

            if success:
                self.parent.after(0, lambda: self.status_label.configure(
                    text=f"Saved: {output_srt.name}",
                    text_color="#2FA572"
                ))
            else:
                self.parent.after(0, lambda: self.status_label.configure(
                    text="Could not generate subtitles",
                    text_color="#FF5555"
                ))

        except Exception as e:
            error_msg = str(e)
            self.parent.after(0, lambda msg=error_msg: self.status_label.configure(
                text=f"Error: {msg}",
                text_color="#FF5555"
            ))
        finally:
            self.parent.after(0, lambda: self.generate_btn.configure(state="normal"))
