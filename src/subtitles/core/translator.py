#!/usr/bin/env python3
"""Core subtitle translation logic."""

from pathlib import Path
from typing import Optional
import srt
from deep_translator import GoogleTranslator
from subtitles.utils.logging_config import get_logger

logger = get_logger()


def find_local_srt(video_path: Path) -> Optional[Path]:
    """Search for a .srt file with the same base name as video."""
    possible_srt = video_path.parent / f"{video_path.stem}.srt"
    return possible_srt if possible_srt.exists() else None


def translate_srt_file(
    input_srt: Path, 
    output_srt: Path, 
    target_lang: str = 'es',
    use_enhanced: bool = True,
    use_parallel: bool = False
) -> bool:
    """Translate SRT file to target language using srt library.
    
    Args:
        input_srt: Path to input SRT file
        output_srt: Path to save translated SRT
        target_lang: Target language code (default: 'es')
        use_enhanced: Ignored (kept for compatibility)
        use_parallel: Ignored (kept for compatibility)
    
    Returns:
        True if translation succeeded
    """
    logger.info(f"Translating {input_srt.name} to {target_lang}")
    
    # Read and parse SRT file
    try:
        content = input_srt.read_text(encoding='utf-8', errors='ignore')
        subtitles = list(srt.parse(content))
    except Exception as e:
        logger.error(f"Failed to parse SRT: {e}")
        return False
    
    if not subtitles:
        logger.error("No subtitles found")
        return False
    
    logger.info(f"Translating {len(subtitles)} subtitle entries")
    
    # Create translator
    translator = GoogleTranslator(source='auto', target=target_lang)
    
    # Translate each subtitle's content
    try:
        for i, sub in enumerate(subtitles):
            if i % 50 == 0:
                logger.info(f"Progress: {i}/{len(subtitles)}")
            
            # Translate the subtitle content
            try:
                sub.content = translator.translate(sub.content)
            except Exception as e:
                logger.warning(f"Failed to translate subtitle {i}: {e}")
                # Keep original on error
        
        # Write translated SRT
        output_content = srt.compose(subtitles)
        output_srt.write_text(output_content, encoding='utf-8')
        logger.info(f"Saved to: {output_srt.name}")
        return True
        
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return False


def find_and_translate_local_srt(
    video_path: Path, 
    output_srt: Path,
    target_lang: str = 'es'
) -> bool:
    """Find local SRT and translate if needed.
    
    Args:
        video_path: Path to video file
        output_srt: Path to save translated SRT
        target_lang: Target language code
    
    Returns:
        True if found and translated successfully
    """
    from subtitles.utils.translate import is_srt_spanish
    
    # Find local SRT
    local_srt = find_local_srt(video_path)
    if not local_srt:
        return False
    
    logger.info(f"Found local .srt file: {local_srt.name}")
    
    # Check if it's already in target language
    if target_lang == 'es' and is_srt_spanish(local_srt):
        logger.info("File is already in Spanish, copying...")
        content = local_srt.read_text(encoding='utf-8', errors='ignore')
        output_srt.write_text(content, encoding='utf-8')
        return True
    
    # Translate to target language
    logger.info(f"Translating to {target_lang}...")
    return translate_srt_file(local_srt, output_srt, target_lang=target_lang)
