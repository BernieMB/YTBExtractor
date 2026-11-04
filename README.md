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
| `--from` | segundos o `minutos:segundos` | Instante inicial del fragmento. Por defecto: `0`. |
| `--to` | segundos o `minutos:segundos` | Instante final del fragmento. Por defecto: final del video. |
| `-h`, `--help` | - | Muestra la ayuda del programa. |

### Descargar un fragmento

Usa `--from` y `--to` para guardar solo un intervalo. Ambos parámetros son opcionales y funcionan con `mp3`, `mp4` y `both`.

Los tiempos son posiciones dentro del video original: `--from 30 --to 90` genera un fragmento de **60 segundos**, no de 90.

```bash
# MP3 desde el segundo 30 hasta el segundo 90
uv run ytb_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" -f mp3 --from 30 --to 90 -o fragmento

# MP4 desde 1:30 hasta 2:45
uv run ytb_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" -f mp4 --from 1:30 --to 2:45 -o fragmento

# MP3 y MP4 desde el minuto 2 hasta el final
uv run ytb_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" -f both --from 2:00 -o fragmento

# Solo los primeros 45 segundos (MP3 por defecto)
uv run ytb_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" --to 45 -o inicio
```

Estos comandos de una línea también se pueden ejecutar en PowerShell.

Formatos de tiempo aceptados:

| Entrada | Equivalencia |
| --- | --- |
| `90` | 90 segundos |
| `1:30` | 90 segundos |
| `12:05` | 725 segundos |
| `90.5` o `1:30.5` | 90,5 segundos |

Los minutos pueden superar `59`. Después de `:`, los segundos deben ser menores que `60`. Se rechazan valores negativos, texto y formatos como `1:60` o `1:02:03`. Para los decimales se utiliza el punto.

Antes de descargar un fragmento, el programa consulta la duración del video y aplica estas reglas:

- Si no se indica `--from`, empieza en el segundo `0`.
- Si no se indica `--to`, termina al final del video.
- Si `--from` es igual o mayor que la duración total, no guarda contenido.
- Si `--to` es igual o menor que `--from`, no guarda contenido.
- Si `--to` supera la duración total, lo ajusta al final real y muestra el ajuste en pantalla.
- Si no puede conocer la duración, o se trata de una lista de reproducción, un directo o un video todavía no emitido, detiene el recorte con un mensaje de error.

Los intervalos inválidos terminan con un código de salida distinto de cero, sin generar archivos multimedia. Con `both`, la validación se realiza antes de comenzar cualquiera de las dos descargas.

FFmpeg recodifica los fragmentos para realizar cortes precisos; esto requiere más procesamiento que copiar los streams. La duración final puede variar ligeramente por los fotogramas y bloques de audio del formato. Si no se indica ninguno de los dos parámetros, se descarga el contenido completo como antes.

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

La salida debe mostrar los formatos `mp3`, `mp4` y `both`, además de las opciones `--output`, `--format`, `--from` y `--to`.

### Pruebas

Ejecuta las pruebas con la biblioteca estándar de Python:

```bash
uv run python -m unittest -v
```

Incluyen validación de tiempos y límites, comprobación de que los rangos inválidos no descargan contenido y recortes reales con archivos sintéticos servidos localmente. Las pruebas de medios requieren FFmpeg y ffprobe en el `PATH`; si no están disponibles, se omiten esas pruebas. No es necesario acceder a YouTube para ejecutarlas.

## Estructura relevante

```text
.
├── ytb_extractor.py  # CLI y lógica de descarga
├── test_ytb_extractor.py # Pruebas de intervalos y recortes de medios
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
