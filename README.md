# YTBExtractor

Herramienta de línea de comandos para descargar el audio o el video de una URL de YouTube. Utiliza [yt-dlp](https://github.com/yt-dlp/yt-dlp) para obtener el contenido y FFmpeg para convertir o combinar los streams descargados.

## Requisitos

- Python 3.12 o superior.
- [uv](https://docs.astral.sh/uv/), para crear y administrar el entorno virtual.
- [FFmpeg](https://ffmpeg.org/download.html), disponible en el `PATH` del sistema.
  - Es necesario para convertir a MP3.
  - También se utiliza para combinar audio y video al generar MP4.
- [Deno](https://docs.deno.com/runtime/getting_started/installation/), disponible en el `PATH`.
  - La configuración actual de yt-dlp usa el solver EJS remoto para resolver algunos desafíos de YouTube.
  - Se necesita conexión a Internet y acceso a GitHub para descargar ese componente.

Comprueba que las herramientas estén disponibles:

```text
python --version
uv --version
ffmpeg -version
deno --version
```

## Instalación

Clona el repositorio y entra en su carpeta:

```bash
git clone <URL_DEL_REPOSITORIO>
cd YTBExtractor
```

Instala las dependencias del proyecto:

```bash
uv sync
```

`uv` utilizará Python 3.12, indicado en `.python-version`, y la versión bloqueada de `yt-dlp` definida en `uv.lock`.

## Uso

La forma general de ejecución es:

```bash
uv run ytb_extractor.py "URL_DE_YOUTUBE" [opciones]
```

Por defecto descarga un MP3 en la carpeta actual. El nombre se genera con el formato `YYYY-MM-DD_HH-MM-SS`.

### Formatos

```bash
# MP3 (opción predeterminada)
uv run ytb_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID"

# MP3 explícitamente
uv run ytb_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" --format mp3

# MP4
uv run ytb_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" --format mp4

# MP3 y MP4
uv run ytb_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" --format both
```

Las opciones disponibles son:

| Opción | Valores | Descripción |
| --- | --- | --- |
| `-f`, `--format` | `mp3`, `mp4`, `both` | Formato de salida. Por defecto: `mp3`. |
| `-o`, `--output` | nombre base | Nombre del archivo sin extensión. Por defecto: fecha y hora actuales. |
| `-h`, `--help` | - | Muestra la ayuda del programa. |

### Nombre y carpeta de salida

El nombre indicado con `-o` se interpreta como un nombre base y no debe incluir la extensión:

```bash
mkdir -p Output
uv run ytb_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --format both \
  --output Output/mi_video
```

El comando anterior genera:

```text
Output/mi_video_audio.mp3
Output/mi_video_video.mp4
```

La carpeta de destino debe existir antes de ejecutar el comando. En PowerShell se puede crear con:

```powershell
New-Item -ItemType Directory -Force Output
uv run ytb_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" -f both -o Output\mi_video
```

Si se solicita un solo formato, el archivo conserva exactamente el nombre base indicado, añadiendo la extensión correspondiente. Los MP3 se generan con calidad preferida de 192 kbps.

## Verificar la instalación

Muestra la ayuda de la aplicación sin descargar ningún video:

```bash
uv run ytb_extractor.py --help
```

La salida debe mostrar los formatos `mp3`, `mp4` y `both`, además de las opciones `--output` y `--format`.

## Estructura relevante

```text
.
├── ytb_extractor.py  # CLI y lógica de descarga
├── pyproject.toml    # Metadatos y dependencias del proyecto
├── uv.lock           # Versiones bloqueadas de las dependencias
├── .python-version   # Versión de Python: 3.12
└── Output/           # Archivos descargados, si se usa esta carpeta
```

`main.py` es un archivo de ejemplo que solo imprime `Hello from ytbextractor!`; no es el punto de entrada del extractor. Para descargar contenido se debe ejecutar `ytb_extractor.py`.

## Solución de problemas

### `ffmpeg` no se reconoce

Instala FFmpeg y asegúrate de que su carpeta `bin` esté incluida en el `PATH`. Después abre una terminal nueva y verifica:

```bash
ffmpeg -version
```

### Fallos relacionados con desafíos de YouTube o EJS

Verifica que Deno esté instalado y disponible en el `PATH`:

```bash
deno --version
```

También se necesita conexión a Internet para que yt-dlp pueda obtener el componente EJS remoto desde GitHub.

### `uv` no se reconoce

Instala uv siguiendo su [guía oficial](https://docs.astral.sh/uv/getting-started/installation/) y reinicia la terminal para actualizar el `PATH`.

### La descarga falla

- Comprueba que la URL corresponda a un video público y accesible.
- Usa la URL de un video individual, no una URL de lista de reproducción.
- Actualiza las dependencias con `uv sync`.
- Lee el mensaje mostrado por yt-dlp; el programa termina con código de error cuando la descarga no puede completarse.

## Consideraciones

- El programa no incluye una interfaz gráfica.
- No configura autenticación ni cookies, por lo que no está preparado para videos privados o contenido que requiera iniciar sesión.
- Respeta los derechos de autor y las condiciones de uso de YouTube. Descarga únicamente contenido que tengas permiso para utilizar.
