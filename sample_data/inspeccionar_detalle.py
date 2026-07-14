import json
from collections import Counter

ARCHIVO = "sample_data/nomenclator.json"

MUNICIPIOS = {
    "TUNJA": "0700001",
    "DUITAMA": "0700079",
    "PAIPA": "0700181",
    "SOGAMOSO": "0700277",
}

with open(ARCHIVO, encoding="utf-8") as archivo:
    datos = json.load(archivo)

print("=" * 80)
print("NIVELES DEFINIDOS EN EL NOMENCLÁTOR")
print("=" * 80)
print(json.dumps(datos.get("levels"), ensure_ascii=False, indent=2))

print("\n" + "=" * 80)
print("ESTRUCTURAS DISPONIBLES EN 'amb'")
print("=" * 80)

for indice, estructura in enumerate(datos.get("amb", [])):
    metadatos = {
        clave: valor
        for clave, valor in estructura.items()
        if clave != "ambitos"
    }

    print(f"\namb[{indice}]")
    print("Metadatos:", json.dumps(metadatos, ensure_ascii=False))
    print("Número de ámbitos:", len(estructura.get("ambitos", [])))

print("\n" + "=" * 80)
print("DETALLE TERRITORIAL POR MUNICIPIO")
print("=" * 80)

for nombre, codigo in MUNICIPIOS.items():
    registros_unicos = {}

    for estructura in datos.get("amb", []):
        for registro in estructura.get("ambitos", []):
            codigo_registro = str(registro.get("c", ""))

            if codigo_registro.startswith(codigo) and codigo_registro != codigo:
                llave = (
                    codigo_registro,
                    registro.get("l"),
                    registro.get("n"),
                    registro.get("m"),
                )
                registros_unicos[llave] = registro

    registros = sorted(
        registros_unicos.values(),
        key=lambda registro: (
            int(registro.get("l", 99)),
            str(registro.get("c", "")),
        ),
    )

    conteo_niveles = Counter(
        registro.get("l")
        for registro in registros
    )

    print("\n" + "-" * 80)
    print(nombre, "| Código municipal:", codigo)
    print("Cantidad de registros descendientes:", len(registros))
    print("Conteo por nivel:", dict(sorted(conteo_niveles.items())))

    for registro in registros[:80]:
        print(
            f"nivel={registro.get('l')} | "
            f"codigo={registro.get('c')} | "
            f"nombre={registro.get('n')} | "
            f"m={registro.get('m')}"
        )

    if len(registros) > 80:
        print(f"... se omitieron {len(registros) - 80} registros adicionales")

print("\nInspección terminada.")
