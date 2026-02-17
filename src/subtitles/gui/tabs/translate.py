"""Translate tab - Translate subtitle files."""
import customtkinter as ctk
from pathlib import Path
from threading import Thread
import sys
import logging

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


class TranslateTab:
    """Translate subtitles tab."""

    def __init__(self, parent):
        self.parent = parent
        self.selected_file = None
        self.create_widgets()
        self.setup_logging()

    def create_widgets(self):
        """Create tab widgets."""
        title = ctk.CTkLabel(
            self.parent,
            text="Translate single subtitle file",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        title.pack(pady=(0, 15))

        # Drop zone
        self.drop_zone = FileDropTarget(
            self.parent,
            file_types=["srt"],
            on_drop=self.on_file_dropped
        )
        self.drop_zone.pack(fill="x", pady=10)

        # Selected file
        self.file_label = ctk.CTkLabel(
            self.parent,
            text="No file selected",
            text_color="gray",
            anchor="w"
        )
        self.file_label.pack(pady=5, fill="x", padx=10)

        # Language selector and Translate button in same row
        controls_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        controls_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(controls_frame, text="Language:").pack(side="left")

        self.lang_selector = LanguageSelector(controls_frame)
        self.lang_selector.pack(side="left", padx=10)

        # Translate button
        self.translate_btn = ctk.CTkButton(
            controls_frame,
            text="Translate",
            command=self.start_translation,
            state="disabled",
            fg_color="#2FA572",
            hover_color="#247559",
            width=100
        )
        self.translate_btn.pack(side="right")

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
        self.translate_btn.configure(state="normal")
        self.status_label.configure(text="")

    def start_translation(self):
        """Start translation in background."""
        if not self.selected_file:
            return

        self.translate_btn.configure(state="disabled")
        self.progress.set(0.1)

        thread = Thread(target=self.translate_file, daemon=True)
        thread.start()

    def translate_file(self):
        """Translate subtitle file."""
        try:
            from subtitles.core.translator import translate_srt_file

            input_file = self.selected_file
            target_lang = self.lang_selector.get_language()
            output_file = input_file.parent / f"{input_file.stem}.{target_lang}{input_file.suffix}"

            self.parent.after(0, lambda: self.status_label.configure(text="Translating..."))
            self.parent.after(0, lambda: self.progress.set(0.5))

            success = translate_srt_file(input_file, output_file, target_lang=target_lang)

            self.parent.after(0, lambda: self.progress.set(1.0))

            if success:
                self.parent.after(0, lambda: self.status_label.configure(
                    text=f"Saved: {output_file.name}",
                    text_color="#2FA572"
                ))
            else:
                self.parent.after(0, lambda: self.status_label.configure(
                    text="Translation failed",
                    text_color="#FF5555"
                ))

        except Exception as e:
            self.parent.after(0, lambda: self.status_label.configure(
                text=f"Error: {str(e)}",
                text_color="#FF5555"
            ))
        finally:
            self.parent.after(0, lambda: self.translate_btn.configure(state="normal"))
