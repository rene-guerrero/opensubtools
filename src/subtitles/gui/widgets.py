"""Custom widgets for the GUI."""
import customtkinter as ctk
from pathlib import Path
from typing import Callable, List
import tkinter as tk


# Supported languages with codes
LANGUAGES = {
    "Spanish": "es",
    "English": "en",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Portuguese": "pt",
    "Russian": "ru",
    "Chinese": "zh",
    "Japanese": "ja",
    "Korean": "ko",
    "Arabic": "ar",
    "Hindi": "hi",
    "Dutch": "nl",
    "Polish": "pl",
    "Turkish": "tr",
}


class FileDropTarget(ctk.CTkFrame):
    """File selector widget."""
    
    def __init__(
        self,
        parent,
        file_types: List[str],
        on_drop: Callable[[Path], None] = None,
        **kwargs
    ):
        self.file_types = [f".{ft.lstrip('.')}" for ft in file_types]
        self.on_drop = on_drop
        self.selected_file = None
        
        super().__init__(
            parent,
            height=80,
            corner_radius=10,
            border_width=2,
            border_color="#3B8ED0",
            **kwargs
        )
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create inner widgets."""
        self.button = ctk.CTkButton(
            self,
            text="Click to Select File",
            command=self.select_file,
            fg_color="transparent",
            border_width=2,
            height=40
        )
        self.button.pack(expand=True, fill="both", padx=5, pady=5)
    
    def select_file(self):
        """Open file dialog."""
        if self.file_types:
            filetypes = [
                (f"{ft.lstrip('.').upper()} files", f"*{ft}")
                for ft in self.file_types
            ]
            filetypes.append(("All files", "*.*"))
        else:
            filetypes = [("All files", "*.*")]
        
        file_path = ctk.filedialog.askopenfilename(filetypes=filetypes)
        if file_path:
            self.selected_file = Path(file_path)
            if self.on_drop:
                self.on_drop(self.selected_file)


class FolderDropTarget(ctk.CTkFrame):
    """Folder selector widget."""
    
    def __init__(
        self,
        parent,
        on_drop: Callable[[Path], None] = None,
        **kwargs
    ):
        self.on_drop = on_drop
        self.selected_folder = None
        
        super().__init__(
            parent,
            height=80,
            corner_radius=10,
            border_width=2,
            border_color="#3B8ED0",
            **kwargs
        )
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create inner widgets."""
        self.button = ctk.CTkButton(
            self,
            text="Click to Select Folder",
            command=self.select_folder,
            fg_color="transparent",
            border_width=2,
            height=40
        )
        self.button.pack(expand=True, fill="both", padx=5, pady=5)
    
    def select_folder(self):
        """Open folder dialog."""
        folder_path = ctk.filedialog.askdirectory()
        if folder_path:
            self.selected_folder = Path(folder_path)
            if self.on_drop:
                self.on_drop(self.selected_folder)


class LanguageSelector(ctk.CTkOptionMenu):
    """Language selector dropdown."""
    
    def __init__(self, parent, **kwargs):
        # Get language names sorted
        lang_names = sorted(LANGUAGES.keys())
        
        super().__init__(
            parent,
            values=lang_names,
            **kwargs
        )
        
        # Default to Spanish
        self.set("Spanish")
    
    def get_language(self) -> str:
        """Get language code."""
        return LANGUAGES[self.get()]
