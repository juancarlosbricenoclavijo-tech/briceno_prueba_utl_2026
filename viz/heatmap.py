from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "puestos_2026.db"
SALIDA = ROOT / "viz" / "heatmap_municipios.png"
MUNICIPIOS = ["TUNJA", "PAIPA", "SOGAMOSO", "DUITAMA"]


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"No existe {DB_PATH}")

    conexion = sqlite3.connect(DB_PATH)
    consulta = """
        SELECT
            mu.nombre AS municipio,
            c.id AS candidato_id,
            c.nombre AS candidato,
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
            par.nombre
    """
    datos = pd.read_sql_query(consulta, conexion)
    conexion.close()

    if datos.empty:
        raise RuntimeError("No hay resultados de candidaturas de Cámara")

    totales_globales = (
        datos.groupby(["candidato_id", "candidato", "partido"], as_index=False)["votos"]
        .sum()
        .sort_values("votos", ascending=False)
        .head(8)
    )
    ids_top = set(totales_globales["candidato_id"].tolist())
    seleccion = datos[datos["candidato_id"].isin(ids_top)].copy()

    totales_municipio = datos.groupby("municipio")["votos"].sum()
    seleccion["porcentaje"] = seleccion.apply(
        lambda fila: 100.0 * fila["votos"] / max(totales_municipio.get(fila["municipio"], 0), 1),
        axis=1,
    )
    seleccion["etiqueta"] = seleccion["candidato"].str.title()

    orden_etiquetas = [
        fila["candidato"].title()
        for _, fila in totales_globales.iterrows()
    ]
    tabla = seleccion.pivot_table(
        index="etiqueta",
        columns="municipio",
        values="porcentaje",
        aggfunc="sum",
        fill_value=0,
    )
    tabla = tabla.reindex(index=orden_etiquetas, columns=MUNICIPIOS, fill_value=0)

    figura, eje = plt.subplots(figsize=(11, 6.5))
    imagen = eje.imshow(tabla.to_numpy(), aspect="auto")
    eje.set_xticks(np.arange(len(tabla.columns)), labels=tabla.columns)
    eje.set_yticks(np.arange(len(tabla.index)), labels=tabla.index)
    eje.set_xlabel("Municipio")
    eje.set_ylabel("Candidatura de Cámara")
    eje.set_title("Top 8 candidaturas de Cámara: participación porcentual por municipio")

    for fila in range(tabla.shape[0]):
        for columna in range(tabla.shape[1]):
            valor = float(tabla.iloc[fila, columna])
            eje.text(columna, fila, f"{valor:.2f}%", ha="center", va="center", fontsize=8)

    figura.colorbar(imagen, ax=eje, label="% del total de votos a candidaturas CA del municipio")
    figura.tight_layout()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(SALIDA, dpi=180, bbox_inches="tight")
    plt.close(figura)
    print(f"[OK] {SALIDA} | {SALIDA.stat().st_size} bytes")


if __name__ == "__main__":
    main()
