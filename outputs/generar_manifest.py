from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "puestos_2026.db"
SALIDA = ROOT / "outputs" / "evaluation_manifest.json"

# EDITE ÚNICAMENTE ESTOS TRES VALORES ANTES DE LA ENTREGA.
META = {
    "nombre": 'Juan Carlos Briceño Clavijo',
    "email": 'jcbricenoc@udistrital.edu.co',
    "repositorio": "https://github.com/juancarlosbricenoclavijo-tech/briceno_prueba_utl_2026",
}

SQL_ARCHIVOS = {
    "3.1_arrastre_verde": ROOT / "sql" / "tarea_3_1.sql",
    "3.2_dominancia_extrema": ROOT / "sql" / "tarea_3_2.sql",
    "3.3_atribucion_deterministica": ROOT / "sql" / "tarea_3_3.sql",
}


def ejecutar_script(ruta: Path) -> str:
    proceso = subprocess.run(
        [sys.executable, str(ruta)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    salida = (proceso.stdout + proceso.stderr).strip()
    if proceso.returncode != 0:
        raise RuntimeError(f"Falló {ruta.relative_to(ROOT)}:\n{salida}")
    return salida


def filas_json(cursor: sqlite3.Cursor, limite: int = 20) -> dict[str, Any]:
    columnas = [columna[0] for columna in cursor.description]
    filas = cursor.fetchmany(limite)
    return {
        "columnas": columnas,
        "filas_muestra": [dict(zip(columnas, fila)) for fila in filas],
        "muestra_limitada_a": limite,
    }


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"No existe {DB_PATH}. Ejecute python scraper.py")

    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row

    integridad = conexion.execute("PRAGMA integrity_check").fetchone()[0]
    municipios = [
        dict(fila)
        for fila in conexion.execute(
            """
            SELECT
                mu.nombre AS municipio,
                COUNT(DISTINCT p.id) AS puestos,
                COUNT(DISTINCT m.id) AS mesas,
                COUNT(DISTINCT tm.eleccion) AS elecciones,
                COUNT(tm.id) AS registros_mesa_eleccion
            FROM municipios AS mu
            JOIN puestos AS p ON p.municipio_id = mu.id
            JOIN mesas AS m ON m.puesto_id = p.id
            LEFT JOIN totales_mesa AS tm ON tm.mesa_id = m.id
            GROUP BY mu.id, mu.nombre
            ORDER BY mu.nombre
            """
        )
    ]
    nombres = {fila["municipio"] for fila in municipios}
    esperados = {"TUNJA", "PAIPA", "SOGAMOSO", "DUITAMA"}
    cantidad_ok = len(nombres & esperados)

    total_mesas = conexion.execute("SELECT COUNT(*) FROM mesas").fetchone()[0]
    total_pares = conexion.execute("SELECT COUNT(*) FROM totales_mesa").fetchone()[0]
    duplicados = conexion.execute(
        """
        SELECT COUNT(*) - COUNT(DISTINCT mesa_id || '-' || eleccion)
        FROM totales_mesa
        """
    ).fetchone()[0]

    sql_resultados: dict[str, Any] = {}
    print(f"{cantidad_ok}/4 municipios")
    for nombre, ruta in SQL_ARCHIVOS.items():
        try:
            cursor = conexion.execute(ruta.read_text(encoding="utf-8"))
            resultado = filas_json(cursor)
            sql_resultados[nombre] = {"estado": "OK", **resultado}
            print(f"SQL OK — {nombre}")
        except Exception as error:
            sql_resultados[nombre] = {"estado": "ERROR", "error": str(error)}
            print(f"SQL ERROR — {nombre}: {error}")

    conexion.close()

    procesos: dict[str, Any] = {}
    for nombre, ruta in {
        "dashboard": ROOT / "dashboard" / "export_data.py",
        "heatmap": ROOT / "viz" / "heatmap.py",
        "scatter": ROOT / "viz" / "scatter.py",
    }.items():
        try:
            salida = ejecutar_script(ruta)
            procesos[nombre] = {"estado": "OK", "salida": salida}
        except Exception as error:
            procesos[nombre] = {"estado": "ERROR", "error": str(error)}

    scatter_salida = procesos.get("scatter", {}).get("salida", "")
    coincidencia = re.search(
        r"r=([-0-9.]+)\s*\|\s*pendiente=([-0-9.]+)\s*\|\s*n_mesas=(\d+)",
        scatter_salida,
    )
    metricas_scatter = None
    if coincidencia:
        metricas_scatter = {
            "r": float(coincidencia.group(1)),
            "pendiente": float(coincidencia.group(2)),
            "n_mesas": int(coincidencia.group(3)),
        }

    archivos = {}
    for ruta in [
        ROOT / "dashboard" / "index.html",
        ROOT / "dashboard" / "data.json",
        ROOT / "viz" / "heatmap_municipios.png",
        ROOT / "viz" / "scatter_ca_se.png",
    ]:
        archivos[str(ruta.relative_to(ROOT))] = {
            "existe": ruta.exists(),
            "bytes": ruta.stat().st_size if ruta.exists() else 0,
        }

    manifest = {
        "meta": META,
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "base_datos": {
            "ruta": str(DB_PATH.relative_to(ROOT)),
            "integridad": integridad,
            "municipios": municipios,
            "municipios_validos": f"{cantidad_ok}/4",
            "mesas": total_mesas,
            "registros_mesa_eleccion": total_pares,
            "duplicados": duplicados,
            "cobertura_completa": total_mesas == 1107 and total_pares == 2214 and duplicados == 0,
        },
        "sql": sql_resultados,
        "procesos": procesos,
        "scatter_metricas": metricas_scatter,
        "archivos": archivos,
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifest generado: {SALIDA.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
