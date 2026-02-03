#!/usr/bin/env python3
"""
Script para extraer subtítulos embebidos de videos, traducirlos del inglés al español
y guardarlos como archivos .srt.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import ffmpeg
import srt
from deep_translator import GoogleTranslator
from tqdm import tqdm


def get_video_files(folder_path):
    """Obtiene todos los archivos de video de una carpeta."""
    video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"Error: La carpeta '{folder_path}' no existe.")
        sys.exit(1)
    
    video_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in video_extensions]
    return sorted(video_files)


def has_embedded_subtitles(video_path):
    """Verifica si un video tiene subtítulos embebidos."""
    try:
        probe = ffmpeg.probe(str(video_path))
        streams = probe.get('streams', [])
        
        for stream in streams:
            if stream.get('codec_type') == 'subtitle':
                return True
        return False
    except Exception as e:
        print(f"Error al analizar {video_path}: {e}")
        return False


def get_subtitle_streams(video_path):
    """Obtiene los streams de subtítulos de un video."""
    try:
        probe = ffmpeg.probe(str(video_path))
        streams = probe.get('streams', [])
        
        subtitle_streams = []
        for i, stream in enumerate(streams):
            if stream.get('codec_type') == 'subtitle':
                subtitle_streams.append({
                    'index': i,
                    'codec': stream.get('codec_name', 'unknown'),
                    'language': stream.get('tags', {}).get('language', 'unknown'),
                    'title': stream.get('tags', {}).get('title', f'Subtítulo {i}')
                })
        return subtitle_streams
    except Exception as e:
        print(f"Error al obtener subtítulos de {video_path}: {e}")
        return []


def extract_subtitles(video_path, output_path, stream_index=0):
    """Extrae subtítulos de un video usando ffmpeg."""
    try:
        # Extraer subtítulos en formato srt
        stream = ffmpeg.input(str(video_path))
        stream = ffmpeg.output(stream, str(output_path), map=f'0:s:{stream_index}')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        return True
    except Exception as e:
        print(f"Error al extraer subtítulos de {video_path}: {e}")
        return False


def translate_text(text, translator, max_retries=3):
    """Traduce texto del inglés al español con reintentos."""
    if not text or not text.strip():
        return text
    
    for attempt in range(max_retries):
        try:
            translated = translator.translate(text)
            return translated
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Error al traducir (después de {max_retries} intentos): {e}")
                return text
            continue
    return text


def translate_srt_file(input_path, output_path, translator):
    """Traduce un archivo SRT del inglés al español."""
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        
        # Parsear subtítulos
        try:
            subtitles = list(srt.parse(srt_content))
        except Exception as e:
            print(f"Error al parsear SRT: {e}")
            # Intentar limpiar el contenido
            srt_content = clean_srt_content(srt_content)
            subtitles = list(srt.parse(srt_content))
        
        # Traducir cada subtítulo
        translated_subtitles = []
        for subtitle in tqdm(subtitles, desc="Traduciendo subtítulos", leave=False):
            translated_content = translate_text(subtitle.content, translator)
            translated_subtitle = srt.Subtitle(
                index=subtitle.index,
                start=subtitle.start,
                end=subtitle.end,
                content=translated_content
            )
            translated_subtitles.append(translated_subtitle)
        
        # Escribir archivo traducido
        translated_srt = srt.compose(translated_subtitles)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated_srt)
        
        return True
    except Exception as e:
        print(f"Error al traducir {input_path}: {e}")
        return False


def clean_srt_content(content):
    """Limpia el contenido SRT para hacerlo parseable."""
    # Eliminar caracteres BOM
    content = content.replace('\ufeff', '')
    
    # Normalizar líneas
    content = re.sub(r'\r\n', '\n', content)
    content = re.sub(r'\r', '\n', content)
    
    # Asegurar que haya líneas en blanco entre subtítulos
    content = re.sub(r'\n\n+', '\n\n', content)
    
    return content.strip()


def process_video(video_path, translator, overwrite=False):
    """Procesa un video: extrae subtítulos y los traduce."""
    video_path = Path(video_path)
    output_srt = video_path.with_suffix('.es.srt')
    temp_srt = video_path.with_suffix('.temp.srt')
    
    # Verificar si ya existe el archivo traducido
    if output_srt.exists() and not overwrite:
        print(f"  ⏭️  Subtítulos ya existen para: {video_path.name}")
        return False
    
    print(f"\n🎬 Procesando: {video_path.name}")
    
    # Verificar si tiene subtítulos embebidos
    if not has_embedded_subtitles(video_path):
        print(f"  ❌ No tiene subtítulos embebidos")
        return False
    
    # Obtener información de streams de subtítulos
    subtitle_streams = get_subtitle_streams(video_path)
    if not subtitle_streams:
        print(f"  ❌ No se pudieron detectar streams de subtítulos")
        return False
    
    print(f"  📋 Encontrados {len(subtitle_streams)} stream(s) de subtítulos")
    
    # Usar el primer stream (generalmente el primario)
    target_stream = 0
    for i, stream in enumerate(subtitle_streams):
        lang = stream['language'].lower()
        if lang in ['eng', 'en', 'english']:
            target_stream = i
            print(f"  ✅ Usando subtítulos en inglés (stream {i})")
            break
    else:
        print(f"  ⚠️  Usando primer stream disponible (stream {target_stream})")
    
    # Extraer subtítulos
    print(f"  📥 Extrayendo subtítulos...")
    if not extract_subtitles(video_path, temp_srt, target_stream):
        return False
    
    # Traducir subtítulos
    print(f"  🌐 Traduciendo al español...")
    if translate_srt_file(temp_srt, output_srt, translator):
        print(f"  ✅ Subtítulos guardados en: {output_srt.name}")
        success = True
    else:
        print(f"  ❌ Error al traducir subtítulos")
        success = False
    
    # Limpiar archivo temporal
    if temp_srt.exists():
        temp_srt.unlink()
    
    return success


def main():
    parser = argparse.ArgumentParser(
        description='Extrae subtítulos embebidos de videos y los traduce al español'
    )
    parser.add_argument(
        'folder',
        help='Carpeta que contiene los videos'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Sobrescribir archivos .srt existentes'
    )
    
    args = parser.parse_args()
    
    # Verificar que ffmpeg esté instalado
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Error: ffmpeg no está instalado o no está en el PATH")
        print("Por favor, instala ffmpeg:")
        print("  Windows: winget install Gyan.FFmpeg")
        print("  Mac: brew install ffmpeg")
        print("  Linux: sudo apt install ffmpeg")
        sys.exit(1)
    
    # Inicializar traductor
    print("🔄 Inicializando traductor...")
    translator = GoogleTranslator(source='en', target='es')
    
    # Obtener archivos de video
    print(f"\n📁 Buscando videos en: {args.folder}")
    video_files = get_video_files(args.folder)
    
    if not video_files:
        print("❌ No se encontraron archivos de video en la carpeta especificada")
        print("Formatos soportados: .mp4, .mkv, .avi, .mov, .wmv, .flv, .webm, .m4v")
        sys.exit(1)
    
    print(f"✅ Encontrados {len(video_files)} archivo(s) de video")
    
    # Procesar cada video
    success_count = 0
    for video_file in video_files:
        if process_video(video_file, translator, args.overwrite):
            success_count += 1
    
    print(f"\n🎉 Proceso completado: {success_count}/{len(video_files)} videos procesados correctamente")


if __name__ == '__main__':
    main()
