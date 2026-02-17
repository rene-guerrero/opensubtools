"""Custom widgets for the GUI."""
import customtkinter as ctk
from pathlib import Path
from typing import Callable, List
import tkinter as tk
from tkinterdnd2 import DND_FILES


# Supported languages with codes and flags
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
    "Swedish": "sv",
    "Vietnamese": "vi",
    "Thai": "th",
    "Indonesian": "id",
    "Greek": "el",
    "Hebrew": "he",
    "Czech": "cs",
    "Romanian": "ro",
    "Hungarian": "hu",
    "Ukrainian": "uk",
}

# Language codes for deep-translator Google
LANG_CODES = {
    "es": "es", "en": "en", "fr": "fr", "de": "de", "it": "it",
    "pt": "pt", "ru": "ru", "zh": "zh-CN", "ja": "ja", "ko": "ko",
    "ar": "ar", "hi": "hi", "nl": "nl", "pl": "pl", "tr": "tr",
    "sv": "sv", "vi": "vi", "th": "th", "id": "id", "el": "el",
    "he": "iw", "cs": "cs", "ro": "ro", "hu": "hu", "uk": "uk",
}

# Flag codes for CDN images
LANG_FLAG_CODES = {
    "Spanish": "es", "English": "gb", "French": "fr", "German": "de",
    "Italian": "it", "Portuguese": "pt", "Russian": "ru", "Chinese": "cn",
    "Japanese": "jp", "Korean": "kr", "Arabic": "sa", "Hindi": "in",
    "Dutch": "nl", "Polish": "pl", "Turkish": "tr", "Swedish": "se",
    "Vietnamese": "vn", "Thai": "th", "Indonesian": "id", "Greek": "gr",
    "Hebrew": "il", "Czech": "cz", "Romanian": "ro", "Hungarian": "hu",
    "Ukrainian": "ua",
}


class FileDropTarget(ctk.CTkFrame):
    """File selector widget with drag and drop support."""
    
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
        self.setup_drag_drop()
    
    def create_widgets(self):
        """Create inner widgets."""
        self.button = ctk.CTkButton(
            self,
            text="Drag & Drop file here\nor Click to Select",
            command=self.select_file,
            fg_color="transparent",
            border_width=2,
            height=40
        )
        self.button.pack(expand=True, fill="both", padx=5, pady=5)
    
    def setup_drag_drop(self):
        """Setup drag and drop support."""
        # Register as drop target
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.on_drag_drop)
    
    def on_drag_drop(self, event):
        """Handle drag and drop event."""
        file_path = event.data.strip('{}')
        if file_path:
            path = Path(file_path)
            # Check if file type matches
            if path.suffix.lower() in [ft.lower() for ft in self.file_types] or not self.file_types:
                self.selected_file = path
                if self.on_drop:
                    self.on_drop(self.selected_file)
    
    def select_file(self):
        """Open file dialog."""
        if self.file_types:
            # Create "Video files" filter with all video extensions combined
            video_extensions = " ".join([f"*{ft}" for ft in self.file_types])
            filetypes = [
                ("Video files", video_extensions),
                ("All files", "*.*")
            ]
        else:
            filetypes = [("All files", "*.*")]
        
        file_path = ctk.filedialog.askopenfilename(filetypes=filetypes)
        if file_path:
            self.selected_file = Path(file_path)
            if self.on_drop:
                self.on_drop(self.selected_file)


class FolderDropTarget(ctk.CTkFrame):
    """Folder selector widget with drag and drop support."""
    
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
        self.setup_drag_drop()
    
    def create_widgets(self):
        """Create inner widgets."""
        self.button = ctk.CTkButton(
            self,
            text="Drag & Drop folder here\nor Click to Select",
            command=self.select_folder,
            fg_color="transparent",
            border_width=2,
            height=40
        )
        self.button.pack(expand=True, fill="both", padx=5, pady=5)
    
    def setup_drag_drop(self):
        """Setup drag and drop support."""
        # Register as drop target
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.on_drag_drop)
    
    def on_drag_drop(self, event):
        """Handle drag and drop event."""
        file_path = event.data.strip('{}')
        if file_path:
            path = Path(file_path)
            # For folders, accept any path
            self.selected_folder = path
            if self.on_drop:
                self.on_drop(self.selected_folder)
    
    def select_folder(self):
        """Open folder dialog."""
        folder_path = ctk.filedialog.askdirectory()
        if folder_path:
            self.selected_folder = Path(folder_path)
            if self.on_drop:
                self.on_drop(self.selected_folder)


class LanguageSelector(ctk.CTkComboBox):
    """Language selector dropdown with flags."""
    
    def __init__(self, parent, **kwargs):
        # Build list with [CODE] Language format
        self._lang_map = {}
        values = []
        
        for name in sorted(LANGUAGES.keys()):
            code = LANG_FLAG_CODES.get(name, name[:2].upper())
            display = f"[{code.upper()}] {name}"
            values.append(display)
            self._lang_map[display] = name
        
        super().__init__(
            parent,
            values=values,
            **kwargs
        )
        
        # Default to Spanish
        self.set("[ES] Spanish")
    
    def get_language(self) -> str:
        """Get language code for translation."""
        display = self.get() or "[ES] Spanish"
        
        # Get language name from display
        name = self._lang_map.get(display, "Spanish")
        code = LANGUAGES[name]
        return LANG_CODES.get(code, code)
    
    def set(self, value):
        """Set the language."""
        if value in LANGUAGES:
            code = LANG_FLAG_CODES.get(value, value[:2].upper())
            display = f"[{code.upper()}] {value}"
            super().set(display)
        elif value in self._lang_map:
            super().set(value)
