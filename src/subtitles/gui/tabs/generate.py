"""Generate tab - Generate subtitles for videos."""
import customtkinter as ctk
from pathlib import Path
from threading import Thread
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from subtitles.gui.widgets import FileDropTarget, LanguageSelector


class GenerateTab:
    """Generate subtitles tab."""

    def __init__(self, parent):
        self.parent = parent
        self.selected_file = None
        
        self.create_widgets()

    def create_widgets(self):
        """Create tab widgets."""
        # Title
        title = ctk.CTkLabel(
            self.parent,
            text="Generate Subtitles",
            font=ctk.CTkFont(size=18, weight="bold")
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
            text_color="gray"
        )
        self.file_label.pack(pady=5)
        
        # Language selector
        lang_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        lang_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(lang_frame, text="Translate to:").pack(side="left")
        
        self.lang_selector = LanguageSelector(lang_frame)
        self.lang_selector.pack(side="left", padx=10)
        
        # Generate button
        self.generate_btn = ctk.CTkButton(
            self.parent,
            text="Generate Subtitles",
            command=self.start_generation,
            state="disabled",
            fg_color="#2FA572",
            hover_color="#247559"
        )
        self.generate_btn.pack(pady=15)
        
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
            from subtitles.core.extractor import extract_english_subtitles, extract_spanish_subtitles
            from subtitles.core.downloader import download_english_subtitle, download_spanish_subtitle
            from subtitles.core.translator import translate_srt_file
            from deep_translator import GoogleTranslator
            
            video_path = self.selected_file
            target_lang = self.lang_selector.get_language()
            output_srt = video_path.parent / f"{video_path.stem}.srt"
            
            self.parent.after(0, lambda: self.progress.set(0.2))
            self.parent.after(0, lambda: self.status_label.configure(text="Checking for existing subtitles..."))
            
            # Try methods in order
            success = False
            
            # 1. Find local SRT
            self.parent.after(0, lambda: self.progress.set(0.3))
            self.parent.after(0, lambda: self.status_label.configure(text="Looking for local .srt file..."))
            
            if find_and_translate_local_srt(video_path, output_srt):
                success = True
                
            # 2. Extract Spanish subtitles
            if not success:
                self.parent.after(0, lambda: self.progress.set(0.4))
                self.parent.after(0, lambda: self.status_label.configure(text="Extracting Spanish subtitles..."))
                
                temp_srt = video_path.parent / f"{video_path.stem}.temp.srt"
                if extract_spanish_subtitles(video_path, temp_srt):
                    temp_srt.rename(output_srt)
                    success = True
                    
            # 3. Extract and translate English
            if not success:
                self.parent.after(0, lambda: self.progress.set(0.6))
                self.parent.after(0, lambda: self.status_label.configure(text="Extracting English subtitles..."))
                
                temp_srt = video_path.parent / f"{video_path.stem}.temp.srt"
                char_count = extract_english_subtitles(video_path, temp_srt)
                
                if char_count and char_count > 0:
                    self.parent.after(0, lambda: self.progress.set(0.7))
                    self.parent.after(0, lambda: self.status_label.configure(text="Translating..."))
                    
                    if translate_srt_file(temp_srt, output_srt):
                        temp_srt.unlink(missing_ok=True)
                        success = True
                        
            # 4. Download subtitles
            if not success:
                self.parent.after(0, lambda: self.progress.set(0.8))
                self.parent.after(0, lambda: self.status_label.configure(text="Downloading subtitles..."))
                
                # Try Spanish first, then English
                downloaded = download_spanish_subtitle(video_path)
                if downloaded:
                    downloaded.rename(output_srt)
                    success = True
                else:
                    downloaded = download_english_subtitle(video_path)
                    if downloaded:
                        translator = GoogleTranslator(source='en', target=target_lang)
                        if translate_srt_file(downloaded, output_srt):
                            downloaded.unlink(missing_ok=True)
                            success = True
                            
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
            self.parent.after(0, lambda: self.status_label.configure(
                text=f"Error: {str(e)}",
                text_color="#FF5555"
            ))
        finally:
            self.parent.after(0, lambda: self.generate_btn.configure(state="normal"))
