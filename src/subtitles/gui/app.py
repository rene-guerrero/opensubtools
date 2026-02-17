"""GUI application for Subtitle Tools."""
import customtkinter as ctk
import sys
from pathlib import Path
from typing import Optional

# Configure CustomTkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

from subtitles.gui.tabs.generate import GenerateTab
from subtitles.gui.tabs.translate import TranslateTab
from subtitles.gui.tabs.sync import SyncTab
from subtitles.gui.tabs.batch import BatchTab


class SubtitleApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # Window configuration
        self.title("Subtitle Tools")
        self.geometry("700x550")
        self.resizable(False, False)
        
        # Center window on screen
        self.center_window()
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Create UI
        self.create_header()
        self.create_tabs()
        self.create_footer()
        
        # Select default tab
        self.tab_view.set("Generate")

    def center_window(self):
        """Center window on screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def create_header(self):
        """Create header with title."""
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="ew")
        
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="Subtitle Tools",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.title_label.pack(side="left")

    def create_tabs(self):
        """Create tab view with all features."""
        self.tab_view = ctk.CTkTabview(self, fg_color="transparent")
        self.tab_view.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        # Add tabs
        self.tab_view.add("Generate")
        self.tab_view.add("Translate")
        self.tab_view.add("Sync")
        self.tab_view.add("Batch")
        
        # Create tab content
        self.generate_tab = GenerateTab(self.tab_view.tab("Generate"))
        self.translate_tab = TranslateTab(self.tab_view.tab("Translate"))
        self.sync_tab = SyncTab(self.tab_view.tab("Sync"))
        self.batch_tab = BatchTab(self.tab_view.tab("Batch"))

    def create_footer(self):
        """Create footer with status."""
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.grid(row=2, column=0, padx=20, pady=(5, 15), sticky="ew")
        
        self.status_label = ctk.CTkLabel(
            self.footer_frame,
            text="Ready",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.status_label.pack(side="left")

    def set_status(self, message: str):
        """Update status message."""
        self.status_label.configure(text=message)
        self.update()


def main():
    """Main entry point."""
    app = SubtitleApp()
    app.mainloop()


if __name__ == "__main__":
    main()
