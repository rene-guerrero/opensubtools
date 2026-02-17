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
            from subtitles.core.extractor import extract_english_subtitles, extract_spanish_subtitles, extract_subtitles_by_language
            from subtitles.core.downloader import download_english_subtitle, download_spanish_subtitle
            from subtitles.core.translator import translate_srt_file
            
            video_path = self.selected_file
            target_lang = self.lang_selector.get_language()
            output_srt = video_path.parent / f"{video_path.stem}.srt"
            
            self.parent.after(0, lambda: self.progress.set(0.2))
            self.parent.after(0, lambda: self.status_label.configure(text="Checking for existing subtitles..."))
            
            # Try methods in order
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
                status_msg = f"Extracting {target_lang} subtitles..." if target_lang != 'es' else "Extracting Spanish subtitles..."
                self.parent.after(0, lambda msg=status_msg: self.status_label.configure(text=msg))
                
                language_code_map = {
                    'en': ['en', 'eng'],
                    'fr': ['fr', 'fra'],
                    'de': ['de', 'deu'],
                    'it': ['it', 'ita'],
                    'pt': ['pt', 'por'],
                    'ru': ['ru', 'rus'],
                    'zh': ['zh', 'zho', 'chi'],
                    'ja': ['ja', 'jpn'],
                    'ko': ['ko', 'kor'],
                    'ar': ['ar', 'ara'],
                    'hi': ['hi', 'hin'],
                    'nl': ['nl', 'nld'],
                    'pl': ['pl', 'pol'],
                    'tr': ['tr', 'tur'],
                    'es': ['es', 'spa']
                }
                lang_codes = language_code_map.get(target_lang, [target_lang])
                
                if extract_subtitles_by_language(video_path, output_srt, lang_codes):
                    success = True
            
            # 3. Extract English and translate to target language
            if not success:
                self.parent.after(0, lambda: self.progress.set(0.5))
                self.parent.after(0, lambda: self.status_label.configure(text="Extracting English subtitles..."))
                
                char_count = extract_english_subtitles(video_path, temp_srt)
                
                if char_count and char_count > 0:
                    self.parent.after(0, lambda: self.progress.set(0.65))
                    self.parent.after(0, lambda: self.status_label.configure(text=f"Translating to {target_lang}..."))
                    
                    if translate_srt_file(temp_srt, output_srt, target_lang=target_lang):
                        temp_srt.unlink(missing_ok=True)
                        success = True
                    else:
                        temp_srt.unlink(missing_ok=True)
            
            # 4. Download and translate if needed
            if not success:
                self.parent.after(0, lambda: self.progress.set(0.75))
                self.parent.after(0, lambda: self.status_label.configure(text="Downloading English subtitles..."))
                
                downloaded = download_english_subtitle(video_path)
                if downloaded:
                    self.parent.after(0, lambda: self.progress.set(0.85))
                    self.parent.after(0, lambda: self.status_label.configure(text=f"Translating to {target_lang}..."))
                    
                    if translate_srt_file(downloaded, output_srt, target_lang=target_lang):
                        downloaded.unlink(missing_ok=True)
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
