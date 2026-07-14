from __future__ import annotations

import re
import sqlite3
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "db" / "schema.sql"

PRIMARY_CAMERA = {"CA": "1", "SE": "0"}


def entero(valor: Any) -> int:
    """Convierte valores numéricos de la API a enteros seguros."""
    if valor in (None, ""):
        return 0
    texto = str(valor).strip().replace(".", "")
    try:
        return int(texto)
    except ValueError:
        return 0


def limpiar_nombre(*partes: Any) -> str:
    texto = " ".join(str(p).strip() for p in partes if p not in (None, ""))
    return re.sub(r"\s+", " ", texto).strip().upper()


def normalizar_nombre(texto: str) -> str:
    texto = unicodedata.normalize("NFD", limpiar_nombre(texto))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z0-9 ]+", "", texto)


def abrir_base(ruta_db: Path | str) -> sqlite3.Connection:
    ruta = Path(ruta_db)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.execute("PRAGMA journal_mode = WAL")
    conexion.execute("PRAGMA synchronous = NORMAL")
    conexion.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conexion


def _insertar_o_buscar(
    conexion: sqlite3.Connection,
    sql_insertar: str,
    parametros: tuple[Any, ...],
    sql_buscar: str,
    parametros_buscar: tuple[Any, ...],
) -> tuple[int, bool]:
    antes = conexion.total_changes
    conexion.execute(sql_insertar, parametros)
    insertado = conexion.total_changes > antes
    fila = conexion.execute(sql_buscar, parametros_buscar).fetchone()
    if fila is None:
        raise RuntimeError("No fue posible recuperar el registro insertado o existente")
    return int(fila[0]), insertado


def asegurar_municipio(
    conexion: sqlite3.Connection, codigo: str, nombre: str
) -> tuple[int, bool]:
    return _insertar_o_buscar(
        conexion,
        "INSERT OR IGNORE INTO municipios(codigo, nombre) VALUES (?, ?)",
        (codigo, nombre),
        "SELECT id FROM municipios WHERE codigo = ?",
        (codigo,),
    )


def asegurar_puesto(
    conexion: sqlite3.Connection,
    municipio_id: int,
    codigo: str,
    nombre: str,
    mesas_esperadas: int,
) -> tuple[int, bool]:
    zona = codigo[7:9] if len(codigo) >= 9 else "00"
    return _insertar_o_buscar(
        conexion,
        """
        INSERT OR IGNORE INTO puestos(
            municipio_id, codigo, nombre, zona, mesas_esperadas
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (municipio_id, codigo, nombre, zona, mesas_esperadas),
        "SELECT id FROM puestos WHERE codigo = ?",
        (codigo,),
    )


def asegurar_mesa(
    conexion: sqlite3.Connection, puesto_id: int, numero: int, codigo: str
) -> tuple[int, bool]:
    return _insertar_o_buscar(
        conexion,
        "INSERT OR IGNORE INTO mesas(puesto_id, numero, codigo) VALUES (?, ?, ?)",
        (puesto_id, numero, codigo),
        "SELECT id FROM mesas WHERE codigo = ?",
        (codigo,),
    )


def asegurar_partido(
    conexion: sqlite3.Connection, eleccion: str, codpar: str, nombre: str
) -> tuple[int, bool]:
    nombre = limpiar_nombre(nombre) or f"PARTIDO {codpar}"
    partido_id, insertado = _insertar_o_buscar(
        conexion,
        "INSERT OR IGNORE INTO partidos(eleccion, codpar, nombre) VALUES (?, ?, ?)",
        (eleccion, str(codpar), nombre),
        "SELECT id FROM partidos WHERE eleccion = ? AND codpar = ?",
        (eleccion, str(codpar)),
    )
    conexion.execute(
        """
        UPDATE partidos
        SET nombre = ?
        WHERE id = ? AND nombre LIKE 'PARTIDO %' AND ? NOT LIKE 'PARTIDO %'
        """,
        (nombre, partido_id, nombre),
    )
    return partido_id, insertado


def asegurar_candidato(
    conexion: sqlite3.Connection,
    partido_id: int,
    codcan: str,
    cedula: str,
    nombre: str,
) -> tuple[int, bool]:
    nombre = limpiar_nombre(nombre) or "SIN NOMBRE"
    return _insertar_o_buscar(
        conexion,
        """
        INSERT OR IGNORE INTO candidatos(
            partido_id, codcan, cedula, nombre, nombre_normalizado
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (partido_id, str(codcan), str(cedula or ""), nombre, normalizar_nombre(nombre)),
        "SELECT id FROM candidatos WHERE partido_id = ? AND codcan = ?",
        (partido_id, str(codcan)),
    )


def _insertar_unico(
    conexion: sqlite3.Connection, sql: str, parametros: tuple[Any, ...]
) -> bool:
    antes = conexion.total_changes
    conexion.execute(sql, parametros)
    return conexion.total_changes > antes


def circunscripcion_principal(datos: Mapping[str, Any], eleccion: str) -> Mapping[str, Any]:
    objetivo = PRIMARY_CAMERA[eleccion]
    for camara in datos.get("camaras", []):
        if str(camara.get("cam")) == objetivo and str(camara.get("cir", "0")) == "0":
            return camara
    raise ValueError(f"No se encontró la circunscripción principal {objetivo} para {eleccion}")


def cargar_mesa(
    conexion: sqlite3.Connection,
    *,
    municipio_codigo: str,
    municipio_nombre: str,
    puesto_codigo: str,
    puesto_nombre: str,
    mesas_esperadas: int,
    numero_mesa: int,
    eleccion: str,
    datos: Mapping[str, Any],
    fuente_url: str,
    nombres_partidos: Mapping[tuple[str, str], str],
) -> Counter:
    conteo: Counter = Counter()

    municipio_id, nuevo = asegurar_municipio(
        conexion, municipio_codigo, municipio_nombre
    )
    conteo["insertadas" if nuevo else "omitidas"] += 1

    puesto_id, nuevo = asegurar_puesto(
        conexion,
        municipio_id,
        puesto_codigo,
        puesto_nombre,
        mesas_esperadas,
    )
    conteo["insertadas" if nuevo else "omitidas"] += 1

    codigo_mesa = f"{puesto_codigo}{numero_mesa:06d}"
    mesa_id, nuevo = asegurar_mesa(conexion, puesto_id, numero_mesa, codigo_mesa)
    conteo["insertadas" if nuevo else "omitidas"] += 1

    totales = datos.get("totales", {}).get("act", {})
    nuevo = _insertar_unico(
        conexion,
        """
        INSERT OR IGNORE INTO totales_mesa(
            mesa_id, eleccion, censo, votantes, abstencion, votos_nulos,
            votos_no_marcados, votos_blancos, votos_validos,
            mesas_escrutadas, fuente_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mesa_id,
            eleccion,
            entero(totales.get("centota")),
            entero(totales.get("votant")),
            entero(totales.get("absten")),
            entero(totales.get("votnul")),
            entero(totales.get("votnma")),
            entero(totales.get("votblan", totales.get("votbla"))),
            entero(totales.get("votval")),
            entero(totales.get("mesesc")),
            fuente_url,
        ),
    )
    conteo["insertadas" if nuevo else "omitidas"] += 1

    camara = circunscripcion_principal(datos, eleccion)
    for item_partido in camara.get("partotabla", []):
        act = item_partido.get("act", item_partido)
        codpar = str(act.get("codpar", "")).strip()
        if not codpar:
            continue

        nombre_partido = nombres_partidos.get(
            (eleccion, codpar), f"PARTIDO {codpar}"
        )
        partido_id, nuevo = asegurar_partido(
            conexion, eleccion, codpar, nombre_partido
        )
        conteo["insertadas" if nuevo else "omitidas"] += 1

        nuevo = _insertar_unico(
            conexion,
            """
            INSERT OR IGNORE INTO resultados_partido(mesa_id, partido_id, votos)
            VALUES (?, ?, ?)
            """,
            (mesa_id, partido_id, entero(act.get("vot"))),
        )
        conteo["insertadas" if nuevo else "omitidas"] += 1

        for candidato in act.get("cantotabla", []):
            votos = entero(candidato.get("vot"))
            if votos <= 0:
                continue

            nombre = limpiar_nombre(
                candidato.get("nomcan"),
                candidato.get("nomcan2"),
                candidato.get("apecan"),
                candidato.get("apecan2"),
            )
            candidato_id, nuevo = asegurar_candidato(
                conexion,
                partido_id,
                str(candidato.get("codcan", "")),
                str(candidato.get("cedula", "")),
                nombre,
            )
            conteo["insertadas" if nuevo else "omitidas"] += 1

            nuevo = _insertar_unico(
                conexion,
                """
                INSERT OR IGNORE INTO resultados_candidato(
                    mesa_id, candidato_id, votos
                ) VALUES (?, ?, ?)
                """,
                (mesa_id, candidato_id, votos),
            )
            conteo["insertadas" if nuevo else "omitidas"] += 1

    return conteo


def registrar_carga(
    conexion: sqlite3.Connection,
    *,
    eleccion: str,
    municipio: str,
    solicitudes: int,
    insertadas: int,
    omitidas: int,
    errores: int,
    detalle: str = "",
) -> None:
    estado = "OK" if errores == 0 else "PARCIAL"
    conexion.execute(
        """
        INSERT INTO carga_log(
            fuente, eleccion, municipio, solicitudes, filas_insertadas,
            filas_omitidas, errores, estado, detalle
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "API Registraduría ACT",
            eleccion,
            municipio,
            solicitudes,
            insertadas,
            omitidas,
            errores,
            estado,
            detalle,
        ),
    )
