from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "puestos_2026.db"
SALIDA = ROOT / "viz" / "scatter_ca_se.png"
MUNICIPIOS = ["TUNJA", "PAIPA", "SOGAMOSO", "DUITAMA"]


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"No existe {DB_PATH}")

    conexion = sqlite3.connect(DB_PATH)
    consulta = """
        WITH votos_mesa AS (
            SELECT
                rp.mesa_id,
                SUM(CASE WHEN par.eleccion = 'CA' THEN rp.votos ELSE 0 END) AS votos_ca,
                SUM(CASE WHEN par.eleccion = 'SE' THEN rp.votos ELSE 0 END) AS votos_se
            FROM resultados_partido AS rp
            JOIN partidos AS par ON par.id = rp.partido_id
            GROUP BY rp.mesa_id
        )
        SELECT
            mu.nombre AS municipio,
            m.codigo AS codigo_mesa,
            vm.votos_ca,
            vm.votos_se
        FROM votos_mesa AS vm
        JOIN mesas AS m ON m.id = vm.mesa_id
        JOIN puestos AS p ON p.id = m.puesto_id
        JOIN municipios AS mu ON mu.id = p.municipio_id
        WHERE vm.votos_ca IS NOT NULL
          AND vm.votos_se IS NOT NULL
        ORDER BY mu.nombre, m.codigo
    """
    datos = pd.read_sql_query(consulta, conexion)
    conexion.close()

    if len(datos) < 2:
        raise RuntimeError("No hay suficientes mesas para calcular regresión")

    x = datos["votos_ca"].astype(float).to_numpy()
    y = datos["votos_se"].astype(float).to_numpy()
    pendiente, intercepto = np.polyfit(x, y, 1)
    r = float(np.corrcoef(x, y)[0, 1])

    figura, eje = plt.subplots(figsize=(9.5, 7))
    for municipio in MUNICIPIOS:
        grupo = datos[datos["municipio"] == municipio]
        if not grupo.empty:
            eje.scatter(
                grupo["votos_ca"],
                grupo["votos_se"],
                label=municipio,
                alpha=0.65,
                s=24,
            )

    x_linea = np.linspace(float(x.min()), float(x.max()), 200)
    y_linea = pendiente * x_linea + intercepto
    eje.plot(x_linea, y_linea, linewidth=2.2, label="Regresión OLS")
    eje.set_xlabel("Votos Cámara por mesa")
    eje.set_ylabel("Votos Senado por mesa")
    eje.set_title("Relación de votos Cámara–Senado por mesa")
    eje.grid(alpha=0.25)
    eje.legend()
    eje.text(
        0.03,
        0.97,
        f"r de Pearson = {r:.3f}\npendiente = {pendiente:.3f}\nn = {len(datos)} mesas",
        transform=eje.transAxes,
        va="top",
        bbox={"boxstyle": "round,pad=0.5", "alpha": 0.85},
    )
    figura.tight_layout()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(SALIDA, dpi=180, bbox_inches="tight")
    plt.close(figura)

    print(f"r={r:.3f} | pendiente={pendiente:.3f} | n_mesas={len(datos)}")


if __name__ == "__main__":
    main()
