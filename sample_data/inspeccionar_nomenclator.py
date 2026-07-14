import json
import unicodedata

ARCHIVO = "sample_data/nomenclator.json"
OBJETIVOS = {"BOYACA", "TUNJA", "PAIPA", "SOGAMOSO", "DUITAMA"}

def normalizar(texto):
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caracter for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )
    return texto.strip().upper()

def recorrer(elemento, ruta="$"):
    if isinstance(elemento, dict):
        coincidencias = {
            normalizar(valor)
            for valor in elemento.values()
            if isinstance(valor, str)
        } & OBJETIVOS

        if coincidencias:
            datos_simples = {
                clave: valor
                for clave, valor in elemento.items()
                if not isinstance(valor, (dict, list))
            }

            print("\n" + "=" * 70)
            print("RUTA:", ruta)
            print("COINCIDENCIA:", ", ".join(sorted(coincidencias)))
            print(
                "DATOS:",
                json.dumps(
                    datos_simples,
                    ensure_ascii=False,
                    indent=2
                )
            )

        for clave, valor in elemento.items():
            recorrer(valor, f"{ruta}.{clave}")

    elif isinstance(elemento, list):
        for indice, valor in enumerate(elemento):
            recorrer(valor, f"{ruta}[{indice}]")

with open(ARCHIVO, encoding="utf-8") as archivo:
    datos = json.load(archivo)

print("Buscando códigos territoriales...")
recorrer(datos)
print("\nBúsqueda terminada.")
