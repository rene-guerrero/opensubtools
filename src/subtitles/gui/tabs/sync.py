"""Sync tab - Synchronize subtitle timing."""
import customtkinter as ctk
from pathlib import Path
from threading import Thread
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from subtitles.gui.widgets import FileDropTarget


class SyncTab:
    """Synchronize subtitles tab."""

    def __init__(self, parent):
        self.parent = parent
        self.selected_file = None
        self.offset_ms = 0
        self.create_widgets()

    def create_widgets(self):
        """Create tab widgets."""
        title = ctk.CTkLabel(
            self.parent,
            text="Sync Subtitles",
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
        
        # Offset slider
        offset_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        offset_frame.pack(fill="x", pady=20)
        
        ctk.CTkLabel(offset_frame, text="Time offset:").pack()
        
        self.offset_label = ctk.CTkLabel(
            offset_frame,
            text="0 ms",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.offset_label.pack(pady=5)
        
        self.offset_slider = ctk.CTkSlider(
            offset_frame,
            from_=-60000,
            to=60000,
            number_of_steps=1200,
            command=self.on_slider_change
        )
        self.offset_slider.pack(fill="x", padx=40)
        
        # Preset buttons
        preset_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        preset_frame.pack(pady=10)
        
        presets = [
            ("-5s", -5000),
            ("-1s", -1000),
            ("+1s", 1000),
            ("+5s", 5000),
        ]
        
        for text, value in presets:
            btn = ctk.CTkButton(
                preset_frame,
                text=text,
                width=60,
                command=lambda v=value: self.set_offset(v)
            )
            btn.pack(side="left", padx=5)
        
        # Sync button
        self.sync_btn = ctk.CTkButton(
            self.parent,
            text="Apply Sync",
            command=self.start_sync,
            state="disabled",
            fg_color="#2FA572",
            hover_color="#247559"
        )
        self.sync_btn.pack(pady=15)
        
        # Status
        self.status_label = ctk.CTkLabel(
            self.parent,
            text="",
            text_color="gray"
        )
        self.status_label.pack(pady=5)

    def on_slider_change(self, value):
        """Handle slider change."""
        self.offset_ms = int(value)
        sign = "+" if self.offset_ms >= 0 else ""
        self.offset_label.configure(text=f"{sign}{self.offset_ms} ms")

    def set_offset(self, value: int):
        """Set offset to preset value."""
        self.offset_ms = value
        self.offset_slider.set(value)
        sign = "+" if value >= 0 else ""
        self.offset_label.configure(text=f"{sign}{value} ms")

    def on_file_dropped(self, file_path: Path):
        """Handle file drop."""
        self.selected_file = file_path
        self.file_label.configure(
            text=f"Selected: {file_path.name}",
            text_color="white"
        )
        self.sync_btn.configure(state="normal")
        self.status_label.configure(text="")

    def start_sync(self):
        """Start sync in background."""
        if not self.selected_file or self.offset_ms == 0:
            return
        
        self.sync_btn.configure(state="disabled")
        
        thread = Thread(target=self.sync_file, daemon=True)
        thread.start()

    def sync_file(self):
        """Synchronize subtitle file."""
        try:
            from subtitles.core.synchronizer import synchronize_srt
            
            input_file = self.selected_file
            output_file = input_file.parent / f"{input_file.stem}.synced{input_file.suffix}"
            
            self.parent.after(0, lambda: self.status_label.configure(text="Synchronizing..."))
            
            result = synchronize_srt(input_file, self.offset_ms, output_file)
            
            self.parent.after(0, lambda: self.status_label.configure(
                text=f"Saved: {result.name}",
                text_color="#2FA572"
            ))
                
        except Exception as e:
            self.parent.after(0, lambda: self.status_label.configure(
                text=f"Error: {str(e)}",
                text_color="#FF5555"
            ))
        finally:
            self.parent.after(0, lambda: self.sync_btn.configure(state="normal"))
