# BRICENO — Prueba Técnica UTL Senado 2026

## Candidato

**Nombre:** Juan Carlos Briceño Clavijo  
Correo: jcbricenoc@udistrital.edu.co
**Repositorio:** https://github.com/juancarlosbricenoclavijo-tech/briceno_prueba_utl_2026

Proyecto desarrollado para construir un pipeline reproducible de resultados electorales de Cámara y Senado en Tunja, Paipa, Sogamoso y Duitama. Incluye extracción desde la API pública de la Registraduría, normalización, almacenamiento en SQLite, consultas SQL analíticas, dashboard HTML autocontenido y visualizaciones en Python.

## Instalación

Requisitos: Python 3.10 o superior y Git.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Pipeline de ejecución

La ejecución completa se realiza desde la raíz del repositorio:

```bash
python scraper.py --preflight
python scraper.py
python dashboard/export_data.py
python viz/heatmap.py
python viz/scatter.py
python outputs/generar_manifest.py
```

También se pueden indicar municipios concretos:

```bash
python scraper.py --municipios TUNJA PAIPA
```

El scraper es idempotente: las restricciones `UNIQUE` y las operaciones `INSERT OR IGNORE` impiden que una segunda ejecución duplique registros. La base final se almacena en `db/puestos_2026.db`.

## API

**Portal base:** `https://resultadospreccongreso2026.registraduria.gov.co`

**Nomenclátor:**

```text
https://resultadospreccongreso2026.registraduria.gov.co/json/nomenclator.json
```

**Patrón de resultados:**

```text
https://resultadospreccongreso2026.registraduria.gov.co/json/ACT/{ELECCION}/{CODIGO_AMBITO}.json
```

- `ACT`: fuente activa indicada por `json/web/config.json`.
- `CA`: Cámara de Representantes.
- `SE`: Senado de la República.
- Municipio: código territorial de siete dígitos.
- Puesto: código de trece dígitos.
- Mesa: código del puesto más el número de mesa con seis dígitos.

Ejemplos:

```text
Tunja Cámara: /json/ACT/CA/0700001.json
Tunja Senado: /json/ACT/SE/0700001.json
Puesto Cámara: /json/ACT/CA/0700001010001.json
Mesa 1 Senado: /json/ACT/SE/0700001010001000001.json
```

Cabeceras utilizadas:

```text
User-Agent: Mozilla/5.0 (compatible; UTLDataPipeline/1.0)
Accept: application/json, text/plain, */*
Referer: https://resultadospreccongreso2026.registraduria.gov.co/
```

Campos JSON relevantes:

- `elec`: identificador de la elección.
- `amb`: código del ámbito territorial consultado.
- `numact`: número de actualización.
- `metota`: mesas totales.
- `mesesc`: mesas escrutadas.
- `centota`: censo electoral.
- `votant`: votantes.
- `absten`: abstención.
- `votnul`: votos nulos.
- `votnma`: votos no marcados.
- `votblan` / `votbla`: votos en blanco.
- `votval`: votos válidos.
- `codpar`: código del partido.
- `vot`: votos del partido o candidatura.
- `codcan`: código de la candidatura.
- `nomcan`, `nomcan2`, `apecan`, `apecan2`: componentes del nombre.

El nomenclátor define los niveles: Colombia, departamento, municipio, zona, comuna, puesto y mesa. Los códigos municipales empleados son Tunja `0700001`, Duitama `0700079`, Paipa `0700181` y Sogamoso `0700277`.

## Municipios en la BD

La cobertura esperada y validada es:

| Municipio | Puestos | Mesas | Registros mesa-elección |
|---|---:|---:|---:|
| Tunja | 26 | 424 | 848 |
| Paipa | 7 | 95 | 190 |
| Sogamoso | 18 | 301 | 602 |
| Duitama | 22 | 287 | 574 |
| **Total** | **73** | **1.107** | **2.214** |

La base contiene resultados de Cámara y Senado para cada mesa, sin duplicados en la combinación `mesa_id + eleccion`.

## Hallazgos principales

1. El análisis de arrastre Verde compara el código `5` de Cámara con el código `57` de Senado y calcula el ratio por puesto. Un ratio superior a `1,0` indica más votos verdes en Senado que en Cámara; un ratio inferior a `1,0` indica el comportamiento contrario.
2. La consulta de dominancia extrema detecta mesas donde una candidatura individual supera el 60 % de los votos obtenidos por su partido. Los votos marcados únicamente por la lista se excluyen del criterio.
3. La atribución determinística distribuye los votos senatoriales de cada partido entre sus candidaturas de Cámara en proporción al peso municipal de cada candidatura. El cálculo se aplica por municipio y después se consolida.
4. El candidato con mayor votación directa de Cámara no necesariamente ocupa el primer lugar en atribución de Senado. La atribución depende también del volumen de votos senatoriales del partido, de la participación relativa del candidato dentro de su lista y de la distribución territorial de esa participación.
5. El scatter CA–SE permite evaluar la asociación lineal entre votos de Cámara y Senado por mesa mediante la pendiente OLS y el coeficiente de Pearson.

## Bonus implementados

- `--preflight`: cuenta puestos, mesas y solicitudes sin descargar resultados.
- Cinco índices SQLite documentados en `db/schema.sql` para acelerar relaciones territoriales, resultados por mesa, búsqueda de partidos y búsqueda normalizada de candidaturas.
- Explicación de por qué el top de Cámara puede diferir del top de atribución de Senado.
- Modo oscuro mediante propiedades CSS personalizadas.
- Botón funcional para exportar a CSV el arrastre Verde del municipio seleccionado.
