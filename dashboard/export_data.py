from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "puestos_2026.db"
DATA_PATH = ROOT / "dashboard" / "data.json"
HTML_PATH = ROOT / "dashboard" / "index.html"

MUNICIPIOS_ORDEN = ["TUNJA", "PAIPA", "SOGAMOSO", "DUITAMA"]

COLORES = {
    ("CA", "5"): "#007C34",
    ("SE", "57"): "#007C34",
    ("CA", "87"): "#7B2D8B",
    ("SE", "92"): "#7B2D8B",
    ("CA", "10"): "#1E477D",
    ("SE", "10"): "#1E477D",
    ("CA", "2"): "#E07B00",
    ("SE", "2"): "#E07B00",
}


def color_partido(eleccion: str, codpar: str) -> str:
    return COLORES.get((str(eleccion), str(codpar)), "#64748B")


def filas_diccionario(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    columnas = [columna[0] for columna in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def leer_sql(nombre: str) -> str:
    return (ROOT / "sql" / nombre).read_text(encoding="utf-8")


def construir_datos() -> dict[str, Any]:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"No existe {DB_PATH}. Ejecute primero: python scraper.py"
        )

    conexion = sqlite3.connect(DB_PATH)

    comparativo = filas_diccionario(
        conexion.execute(
            """
            SELECT
                mu.nombre AS municipio,
                SUM(rp.votos) AS votos_ca
            FROM resultados_partido AS rp
            JOIN partidos AS par
                ON par.id = rp.partido_id
               AND par.eleccion = 'CA'
            JOIN mesas AS m ON m.id = rp.mesa_id
            JOIN puestos AS p ON p.id = m.puesto_id
            JOIN municipios AS mu ON mu.id = p.municipio_id
            GROUP BY mu.nombre
            ORDER BY votos_ca DESC
            """
        )
    )

    top_candidatos = filas_diccionario(
        conexion.execute(
            """
            SELECT
                mu.nombre AS municipio,
                c.nombre AS candidato,
                par.codpar,
                par.nombre AS partido,
                SUM(rc.votos) AS votos
            FROM resultados_candidato AS rc
            JOIN candidatos AS c ON c.id = rc.candidato_id
            JOIN partidos AS par
                ON par.id = c.partido_id
               AND par.eleccion = 'CA'
            JOIN mesas AS m ON m.id = rc.mesa_id
            JOIN puestos AS p ON p.id = m.puesto_id
            JOIN municipios AS mu ON mu.id = p.municipio_id
            WHERE c.codcan <> '0'
              AND c.nombre <> 'SOLO POR LA LISTA'
            GROUP BY
                mu.nombre,
                c.id,
                c.nombre,
                par.codpar,
                par.nombre
            ORDER BY mu.nombre, votos DESC
            """
        )
    )

    lideres_senado = filas_diccionario(
        conexion.execute(
            """
            WITH votos AS (
                SELECT
                    mu.nombre AS municipio,
                    par.codpar,
                    par.nombre AS partido,
                    SUM(rp.votos) AS votos
                FROM resultados_partido AS rp
                JOIN partidos AS par
                    ON par.id = rp.partido_id
                   AND par.eleccion = 'SE'
                JOIN mesas AS m ON m.id = rp.mesa_id
                JOIN puestos AS p ON p.id = m.puesto_id
                JOIN municipios AS mu ON mu.id = p.municipio_id
                GROUP BY
                    mu.nombre,
                    par.codpar,
                    par.nombre
            ),
            ordenados AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY municipio
                        ORDER BY votos DESC, partido
                    ) AS posicion
                FROM votos
            )
            SELECT municipio, codpar, partido, votos
            FROM ordenados
            WHERE posicion = 1
            ORDER BY municipio
            """
        )
    )

    arrastre = filas_diccionario(
        conexion.execute(leer_sql("tarea_3_1.sql"))
    )

    conexion.close()

    top_por_municipio: dict[str, list[dict[str, Any]]] = {
        municipio: [] for municipio in MUNICIPIOS_ORDEN
    }
    for fila in top_candidatos:
        municipio = fila["municipio"]
        if municipio in top_por_municipio and len(top_por_municipio[municipio]) < 10:
            fila["color"] = color_partido("CA", str(fila["codpar"]))
            top_por_municipio[municipio].append(fila)

    lider_por_municipio: dict[str, dict[str, Any]] = {}
    for fila in lideres_senado:
        fila["color"] = color_partido("SE", str(fila["codpar"]))
        lider_por_municipio[fila["municipio"]] = fila

    arrastre_por_municipio: dict[str, list[dict[str, Any]]] = {
        municipio: [] for municipio in MUNICIPIOS_ORDEN
    }
    for fila in arrastre:
        if fila["municipio"] in arrastre_por_municipio:
            arrastre_por_municipio[fila["municipio"]].append(fila)

    comparativo_ordenado = sorted(
        comparativo,
        key=lambda fila: MUNICIPIOS_ORDEN.index(fila["municipio"])
        if fila["municipio"] in MUNICIPIOS_ORDEN
        else 999,
    )

    return {
        "meta": {
            "titulo": "Pipeline de Datos Electorales · Boyacá 2026",
            "fuente": "Registraduría Nacional — resultados de preconteo 2026",
            "municipios": MUNICIPIOS_ORDEN,
        },
        "comparativo": comparativo_ordenado,
        "por_municipio": {
            municipio: {
                "top_candidatos_ca": top_por_municipio.get(municipio, []),
                "lider_senado": lider_por_municipio.get(municipio),
                "arrastre_verde": arrastre_por_municipio.get(municipio, []),
            }
            for municipio in MUNICIPIOS_ORDEN
        },
    }


def insertar_datos_en_html(datos: dict[str, Any]) -> None:
    if not HTML_PATH.exists():
        raise FileNotFoundError(f"No existe la plantilla {HTML_PATH}")

    html = HTML_PATH.read_text(encoding="utf-8")
    json_embebido = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    patron = re.compile(
        r"/\*__DATA_START__\*/.*?/\*__DATA_END__\*/",
        flags=re.DOTALL,
    )
    reemplazo = f"/*__DATA_START__*/{json_embebido}/*__DATA_END__*/"
    html_nuevo, reemplazos = patron.subn(reemplazo, html, count=1)
    if reemplazos != 1:
        raise RuntimeError("No se encontró el marcador de datos en index.html")
    HTML_PATH.write_text(html_nuevo, encoding="utf-8")


def main() -> None:
    datos = construir_datos()
    DATA_PATH.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    insertar_datos_en_html(datos)
    print(f"[OK] Datos exportados: {DATA_PATH}")
    print(f"[OK] Dashboard autocontenido actualizado: {HTML_PATH}")
    print(f"[OK] Municipios: {len(datos['meta']['municipios'])}")


if __name__ == "__main__":
    main()
