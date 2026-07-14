from __future__ import annotations

import argparse
import json
import threading
import time
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from db.etl import abrir_base, cargar_mesa, registrar_carga

ROOT = Path(__file__).resolve().parents[1]
DB_DEFAULT = ROOT / "db" / "puestos_2026.db"
NOMENCLATOR_LOCAL = ROOT / "sample_data" / "nomenclator.json"
NOMENCLATOR_URL = (
    "https://resultadospreccongreso2026.registraduria.gov.co/json/nomenclator.json"
)
BASE_RESULTADOS = (
    "https://resultadospreccongreso2026.registraduria.gov.co/json/ACT"
)

MUNICIPIOS = {
    "TUNJA": "0700001",
    "DUITAMA": "0700079",
    "PAIPA": "0700181",
    "SOGAMOSO": "0700277",
}
ELECCIONES = ("CA", "SE")

NOMBRES_CONOCIDOS = {
    ("CA", "5"): "ALIANZA VERDE",
    ("SE", "57"): "ALIANZA VERDE",
    ("CA", "87"): "PACTO HISTÓRICO",
    ("SE", "92"): "PACTO HISTÓRICO",
    ("CA", "10"): "CENTRO DEMOCRÁTICO",
    ("SE", "10"): "CENTRO DEMOCRÁTICO",
    ("CA", "2"): "PARTIDO CONSERVADOR COLOMBIANO",
    ("SE", "2"): "PARTIDO CONSERVADOR COLOMBIANO",
}

_thread_local = threading.local()


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.strip().upper())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def sesion_http() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        retry = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=0.7,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
        )
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; UTLDataPipeline/1.0)",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://resultadospreccongreso2026.registraduria.gov.co/",
            }
        )
        session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=12))
        _thread_local.session = session
    return _thread_local.session


def descargar_json(url: str, timeout: int = 45) -> dict[str, Any]:
    respuesta = sesion_http().get(url, timeout=timeout)
    respuesta.raise_for_status()
    return respuesta.json()


def cargar_nomenclator() -> dict[str, Any]:
    NOMENCLATOR_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    if NOMENCLATOR_LOCAL.exists() and NOMENCLATOR_LOCAL.stat().st_size > 1000:
        print(f"[INFO] Nomenclátor local: {NOMENCLATOR_LOCAL}")
        with NOMENCLATOR_LOCAL.open(encoding="utf-8") as archivo:
            return json.load(archivo)

    print("[INFO] Descargando nomenclátor oficial...")
    datos = descargar_json(NOMENCLATOR_URL, timeout=90)
    with NOMENCLATOR_LOCAL.open("w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False)
    return datos


def extraer_puestos(
    nomenclator: dict[str, Any], codigo_municipio: str
) -> list[dict[str, Any]]:
    unicos: dict[str, dict[str, Any]] = {}
    for estructura in nomenclator.get("amb", []):
        for registro in estructura.get("ambitos", []):
            codigo = str(registro.get("c", ""))
            if int(registro.get("l", 0) or 0) != 6:
                continue
            if not codigo.startswith(codigo_municipio):
                continue
            unicos[codigo] = {
                "codigo": codigo,
                "nombre": str(registro.get("n", "PUESTO SIN NOMBRE")).strip(),
                "mesas": int(registro.get("m", 0) or 0),
            }
    return sorted(unicos.values(), key=lambda x: x["codigo"])


def extraer_nombres_partidos(nomenclator: dict[str, Any]) -> dict[tuple[str, str], str]:
    resultado = dict(NOMBRES_CONOCIDOS)
    mapa_eleccion = {"1": "SE", "2": "CA"}

    def recorrer(objeto: Any, eleccion: str | None = None) -> None:
        if isinstance(objeto, dict):
            eleccion_local = eleccion
            valor_eleccion = objeto.get("elec")
            if valor_eleccion is not None:
                eleccion_local = mapa_eleccion.get(str(valor_eleccion), eleccion_local)

            codigo = objeto.get("codpar")
            if codigo is None and "c" in objeto:
                codigo = objeto.get("c")

            nombre = None
            for clave in ("nompar", "nombre", "n", "despar", "descripcion", "sigla", "s"):
                valor = objeto.get(clave)
                if isinstance(valor, str) and valor.strip():
                    nombre = valor.strip().upper()
                    break

            if eleccion_local and codigo is not None and nombre:
                codigo_texto = str(codigo).strip()
                if codigo_texto.isdigit() and len(codigo_texto) <= 4:
                    resultado.setdefault((eleccion_local, codigo_texto), nombre)

            for valor in objeto.values():
                recorrer(valor, eleccion_local)

        elif isinstance(objeto, list):
            for elemento in objeto:
                recorrer(elemento, eleccion)

    recorrer(nomenclator.get("partidos", []))
    return resultado


def construir_tareas(
    nomenclator: dict[str, Any], municipios: list[str]
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    tareas: list[dict[str, Any]] = []
    puestos_por_municipio: dict[str, list[dict[str, Any]]] = {}

    for municipio in municipios:
        codigo_municipio = MUNICIPIOS[municipio]
        puestos = extraer_puestos(nomenclator, codigo_municipio)
        puestos_por_municipio[municipio] = puestos

        for puesto in puestos:
            for numero_mesa in range(1, puesto["mesas"] + 1):
                codigo_mesa = f"{puesto['codigo']}{numero_mesa:06d}"
                for eleccion in ELECCIONES:
                    tareas.append(
                        {
                            "municipio": municipio,
                            "municipio_codigo": codigo_municipio,
                            "puesto_codigo": puesto["codigo"],
                            "puesto_nombre": puesto["nombre"],
                            "mesas_esperadas": puesto["mesas"],
                            "numero_mesa": numero_mesa,
                            "eleccion": eleccion,
                            "url": f"{BASE_RESULTADOS}/{eleccion}/{codigo_mesa}.json",
                        }
                    )

    return tareas, puestos_por_municipio


def imprimir_preflight(
    municipios: list[str], puestos_por_municipio: dict[str, list[dict[str, Any]]]
) -> None:
    total_puestos = 0
    total_mesas = 0
    print("\nPREFLIGHT — no descarga resultados\n")
    print(f"{'MUNICIPIO':12} {'PUESTOS':>8} {'MESAS':>8} {'SOLICITUDES':>12}")
    print("-" * 44)
    for municipio in municipios:
        puestos = puestos_por_municipio[municipio]
        mesas = sum(p["mesas"] for p in puestos)
        total_puestos += len(puestos)
        total_mesas += mesas
        print(f"{municipio:12} {len(puestos):8d} {mesas:8d} {mesas * 2:12d}")
    print("-" * 44)
    print(f"{'TOTAL':12} {total_puestos:8d} {total_mesas:8d} {total_mesas * 2:12d}")
    print("Elecciones incluidas: CA (Cámara) y SE (Senado)")


def obtener_tarea(tarea: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    inicio = time.perf_counter()
    datos = descargar_json(tarea["url"])
    tarea = dict(tarea)
    tarea["segundos"] = time.perf_counter() - inicio
    return tarea, datos


def ejecutar(args: argparse.Namespace) -> int:
    solicitados = [normalizar(m) for m in args.municipios]
    desconocidos = [m for m in solicitados if m not in MUNICIPIOS]
    if desconocidos:
        raise SystemExit(
            "Municipios no válidos: "
            + ", ".join(desconocidos)
            + ". Opciones: "
            + ", ".join(MUNICIPIOS)
        )

    nomenclator = cargar_nomenclator()
    nombres_partidos = extraer_nombres_partidos(nomenclator)
    tareas, puestos_por_municipio = construir_tareas(nomenclator, solicitados)

    if args.preflight:
        imprimir_preflight(solicitados, puestos_por_municipio)
        return 0

    print(f"[INFO] Base de datos: {args.db}")
    print(f"[INFO] Municipios: {', '.join(solicitados)}")
    print(f"[INFO] Solicitudes de mesa programadas: {len(tareas)}")
    print(f"[INFO] Trabajadores concurrentes: {args.workers}\n")

    conexion = abrir_base(args.db)
    conteos_grupo: dict[tuple[str, str], Counter] = defaultdict(Counter)
    completadas = 0
    inicio_total = time.perf_counter()

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as ejecutor:
            futuros = {ejecutor.submit(obtener_tarea, tarea): tarea for tarea in tareas}

            for futuro in as_completed(futuros):
                tarea_original = futuros[futuro]
                grupo = (tarea_original["municipio"], tarea_original["eleccion"])
                conteos_grupo[grupo]["solicitudes"] += 1

                try:
                    tarea, datos = futuro.result()
                    conteo = cargar_mesa(
                        conexion,
                        municipio_codigo=tarea["municipio_codigo"],
                        municipio_nombre=tarea["municipio"],
                        puesto_codigo=tarea["puesto_codigo"],
                        puesto_nombre=tarea["puesto_nombre"],
                        mesas_esperadas=tarea["mesas_esperadas"],
                        numero_mesa=tarea["numero_mesa"],
                        eleccion=tarea["eleccion"],
                        datos=datos,
                        fuente_url=tarea["url"],
                        nombres_partidos=nombres_partidos,
                    )
                    conteos_grupo[grupo].update(conteo)
                except Exception as error:  # continúa para registrar carga parcial
                    conteos_grupo[grupo]["errores"] += 1
                    print(
                        f"[ERROR] {tarea_original['municipio']} "
                        f"{tarea_original['eleccion']} "
                        f"puesto={tarea_original['puesto_codigo']} "
                        f"mesa={tarea_original['numero_mesa']}: {error}"
                    )

                completadas += 1
                if completadas % 25 == 0 or completadas == len(tareas):
                    conexion.commit()
                    transcurrido = time.perf_counter() - inicio_total
                    velocidad = completadas / transcurrido if transcurrido else 0
                    restantes = len(tareas) - completadas
                    eta = restantes / velocidad if velocidad else 0
                    print(
                        f"[PROGRESO] {completadas}/{len(tareas)} "
                        f"({completadas / len(tareas):.1%}) | "
                        f"{velocidad:.1f} solicitudes/s | ETA {eta / 60:.1f} min"
                    )

        for (municipio, eleccion), conteo in sorted(conteos_grupo.items()):
            registrar_carga(
                conexion,
                eleccion=eleccion,
                municipio=municipio,
                solicitudes=conteo["solicitudes"],
                insertadas=conteo["insertadas"],
                omitidas=conteo["omitidas"],
                errores=conteo["errores"],
                detalle="Carga de resultados por mesa",
            )
        conexion.commit()

        print("\nRESUMEN DE CARGA")
        print("-" * 78)
        print(
            f"{'MUNICIPIO':12} {'ELEC':5} {'SOLIC.':>8} "
            f"{'INSERT.':>10} {'OMITIDAS':>10} {'ERRORES':>8}"
        )
        print("-" * 78)
        for (municipio, eleccion), conteo in sorted(conteos_grupo.items()):
            print(
                f"{municipio:12} {eleccion:5} {conteo['solicitudes']:8d} "
                f"{conteo['insertadas']:10d} {conteo['omitidas']:10d} "
                f"{conteo['errores']:8d}"
            )

        filas = conexion.execute(
            """
            SELECT m.nombre, COUNT(DISTINCT me.id) AS mesas,
                   COUNT(DISTINCT tm.eleccion) AS elecciones
            FROM municipios m
            JOIN puestos p ON p.municipio_id = m.id
            JOIN mesas me ON me.puesto_id = p.id
            LEFT JOIN totales_mesa tm ON tm.mesa_id = me.id
            GROUP BY m.id, m.nombre
            ORDER BY m.nombre
            """
        ).fetchall()
        print("\nMUNICIPIOS EN LA BD")
        for fila in filas:
            print(
                f"- {fila['nombre']}: {fila['mesas']} mesas | "
                f"{fila['elecciones']} elecciones"
            )

        print(
            f"\n[OK] Pipeline terminado en "
            f"{(time.perf_counter() - inicio_total) / 60:.1f} minutos"
        )
        return 0
    finally:
        conexion.close()


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extrae resultados Cámara y Senado para municipios de Boyacá 2026."
    )
    parser.add_argument(
        "--municipios",
        nargs="+",
        default=list(MUNICIPIOS),
        help="Municipios a procesar. Por defecto: los cuatro requeridos.",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Muestra puestos, mesas y solicitudes sin descargar resultados.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Número de descargas concurrentes (por defecto: 8).",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DB_DEFAULT,
        help="Ruta de la base SQLite.",
    )
    return parser


def main() -> int:
    return ejecutar(construir_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
