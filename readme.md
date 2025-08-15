# py-PPI-analysis

Análisis y visualización de bonos y letras del mercado argentino utilizando datos de Portfolio Personal Inversiones (PPI).

## Descripción

Este proyecto permite descargar, procesar y analizar información financiera de bonos y letras argentinas a través de la API de PPI. Incluye notebooks para el análisis de rendimientos, simulaciones, visualización interactiva y exportación de resultados a Excel y HTML.

## Estructura del proyecto

- `test/`: Notebooks de análisis y visualización.
- `output/`: Resultados generados (archivos Excel, HTML, etc). Esta carpeta se sube vacía al repositorio.
- `requirements.txt`: Dependencias del proyecto.
- `setup.py`: Configuración de instalación.
- `.env`: Variables de entorno (usuario y contraseña de PPI, no subir a git).

## Instalación

1. Clona el repositorio:
   ```sh
   git clone https://github.com/MartinBasualdo0/pyPPI-analysis.git
   cd pyPPI-analysis
   ```
2. Instala las dependencias:
   ```sh
   pip install -r requirements.txt
   ```
3. Crea un archivo `.env` en la raíz con tu usuario y contraseña de PPI:
   ```env
   PPI_USER=tu_usuario
   PPI_PASSWORD=tu_contraseña
   ```

## Uso

Abre los notebooks en la carpeta `test/` y ejecuta las celdas. Los resultados se guardarán en la carpeta `output/`.

## Notebooks principales

- `get_on_data_tir.ipynb`: Análisis de TIR de obligaciones negociables.
- `letras_data.ipynb`: Análisis de letras.
- `ons_hist.ipynb`: Historial de precios y flujos de ONs.

## Notas

- No subas tu archivo `.env` ni archivos de salida a git.
- La carpeta `output/` se sube vacía (ver `.gitignore`).

## Autor

Martin Basualdo
