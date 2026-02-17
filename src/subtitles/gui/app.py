"""GUI application for Subtitle Tools."""
import customtkinter as ctk
import sys
from pathlib import Path
from typing import Optional
from tkinterdnd2 import TkinterDnD, DND_FILES

# Configure CustomTkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

from subtitles.gui.tabs.generate import GenerateTab
from subtitles.gui.tabs.translate import TranslateTab
from subtitles.gui.tabs.sync import SyncTab
from subtitles.gui.tabs.batch import BatchTab


class SubtitleApp(ctk.CTk, TkinterDnD.DnDWrapper):
    """Main application window with drag and drop support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

        # Window configuration
        self.title("Subtitle Tools")
        self.geometry("380x500")
        self.resizable(False, False)

        # Configure grid
        self.grid_columnconfigure(0, weight=1)

        # Center window
        self.center_window()

        # Create UI
        self.create_tabs()

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

    def create_tabs(self):
        """Create tab view with all features."""
        self.tab_view = ctk.CTkTabview(self, fg_color="transparent")
        self.tab_view.grid(row=0, column=0, padx=20, pady=10, sticky="n")

        # Add tabs (Sync and Batch hidden for now)
        self.tab_view.add("Generate")
        self.tab_view.add("Translate")
        # self.tab_view.add("Sync")
        self.tab_view.add("Batch")

        # Create tab content
        self.generate_tab = GenerateTab(self.tab_view.tab("Generate"))
        self.translate_tab = TranslateTab(self.tab_view.tab("Translate"))
        # self.sync_tab = SyncTab(self.tab_view.tab("Sync"))
        self.batch_tab = BatchTab(self.tab_view.tab("Batch"))


def main():
    """Main entry point."""
    app = SubtitleApp()
    app.mainloop()


if __name__ == "__main__":
    main()
