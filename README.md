# Extractor y Traductor de Subtítulos

Script de Python para extraer subtítulos embebidos de archivos de video, traducirlos del inglés al español y guardarlos como archivos `.srt`.

## Requisitos

- Python 3.12
- FFmpeg (debe estar instalado y en el PATH)

### Instalar FFmpeg

**Windows:**
```bash
winget install Gyan.FFmpeg
```

**Mac:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

## Instalación

1. Clonar o descargar este repositorio
2. Crear y activar el entorno virtual:
```bash
py -3.12 -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

## Uso

```bash
python extract_and_translate.py <ruta_de_la_carpeta>
```

### Opciones

- `--overwrite`: Sobrescribir archivos `.srt` existentes

### Ejemplo

```bash
python extract_and_translate.py "C:\Users\TuUsuario\Videos\MisPeliculas"
```

## Formatos soportados

- .mp4
- .mkv
- .avi
- .mov
- .wmv
- .flv
- .webm
- .m4v

## Características

- ✅ Detecta automáticamente subtítulos embebidos
- ✅ Extrae subtítulos en formato SRT
- ✅ Traduce del inglés al español usando Google Translate
- ✅ Preserva los tiempos originales de los subtítulos
- ✅ Procesa múltiples videos en batch
- ✅ Muestra progreso con barras de progreso
- ✅ Manejo de errores y reintentos en la traducción

## Notas

- La traducción se realiza mediante la API gratuita de Google Translate
- Puede haber límites de rate en la traducción para archivos muy grandes
- Los subtítulos traducidos se guardan con el mismo nombre del video pero con extensión `.es.srt`
