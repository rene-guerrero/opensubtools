"""Translate tab - Translate subtitle files."""
import customtkinter as ctk
from pathlib import Path
from threading import Thread
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from subtitles.gui.widgets import FileDropTarget, LanguageSelector


class TranslateTab:
    """Translate subtitles tab."""

    def __init__(self, parent):
        self.parent = parent
        self.selected_file = None
        self.create_widgets()

    def create_widgets(self):
        """Create tab widgets."""
        title = ctk.CTkLabel(
            self.parent,
            text="Translate Subtitles",
            font=ctk.CTkFont(size=18, weight="bold")
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
            text_color="gray"
        )
        self.file_label.pack(pady=5)
        
        # Language selector
        lang_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        lang_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(lang_frame, text="Translate to:").pack(side="left")
        
        self.lang_selector = LanguageSelector(lang_frame)
        self.lang_selector.pack(side="left", padx=10)
        
        # Translate button
        self.translate_btn = ctk.CTkButton(
            self.parent,
            text="Translate",
            command=self.start_translation,
            state="disabled",
            fg_color="#2FA572",
            hover_color="#247559"
        )
        self.translate_btn.pack(pady=15)
        
        # Progress
        self.progress = ctk.CTkProgressBar(self.parent, width=400)
        self.progress.pack(pady=5)
        self.progress.set(0)
        
        # Status
        self.status_label = ctk.CTkLabel(
            self.parent,
            text="",
            text_color="gray"
        )
        self.status_label.pack(pady=5)

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
            
            # Translate using the core function
            success = translate_srt_file(input_file, output_file)
            
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
