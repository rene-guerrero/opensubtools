"""Batch tab - Batch process videos."""
import customtkinter as ctk
from pathlib import Path
from threading import Thread
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from subtitles.gui.widgets import FolderDropTarget, LanguageSelector


class BatchTab:
    """Batch processing tab."""

    def __init__(self, parent):
        self.parent = parent
        self.selected_folder = None
        self.create_widgets()

    def create_widgets(self):
        """Create tab widgets."""
        title = ctk.CTkLabel(
            self.parent,
            text="Batch Process",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(pady=(0, 15))
        
        # Drop zone for folder
        self.drop_zone = FolderDropTarget(
            self.parent,
            on_drop=self.on_folder_dropped
        )
        self.drop_zone.pack(fill="x", pady=10)
        
        # Selected folder
        self.folder_label = ctk.CTkLabel(
            self.parent,
            text="No folder selected",
            text_color="gray"
        )
        self.folder_label.pack(pady=5)
        
        # Language selector
        lang_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        lang_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(lang_frame, text="Translate to:").pack(side="left")
        
        self.lang_selector = LanguageSelector(lang_frame)
        self.lang_selector.pack(side="left", padx=10)
        
        # Info label
        info_label = ctk.CTkLabel(
            self.parent,
            text="Processes all video files in the selected folder\nand subfolders",
            text_color="gray",
            font=ctk.CTkFont(size=12)
        )
        info_label.pack(pady=10)
        
        # Process button
        self.process_btn = ctk.CTkButton(
            self.parent,
            text="Process Folder",
            command=self.start_batch,
            state="disabled",
            fg_color="#2FA572",
            hover_color="#247559"
        )
        self.process_btn.pack(pady=15)
        
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
        
        # Results
        self.results_text = ctk.CTkTextbox(self.parent, height=100, width=450)
        self.results_text.pack(pady=10)
        self.results_text.configure(state="disabled")

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
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.configure(state="disabled")
        
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
            
            self.parent.after(0, lambda: self.results_text.configure(state="normal"))
            self.parent.after(0, lambda: self.results_text.insert("1.0", 
                f"Processed: {total}\nSuccess: {success}\nFailed: {failed}\nSkipped: {skipped}"
            ))
            self.parent.after(0, lambda: self.results_text.configure(state="disabled"))
            
        except Exception as e:
            self.parent.after(0, lambda: self.status_label.configure(
                text=f"Error: {str(e)}",
                text_color="#FF5555"
            ))
        finally:
            self.parent.after(0, lambda: self.process_btn.configure(state="normal"))
