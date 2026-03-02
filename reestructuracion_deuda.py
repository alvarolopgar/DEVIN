"""
Política de Reestructuración de Deuda
======================================
Cruza clientes.csv y prestamos.json, calcula el DTI (Cuota mensual / Salario)
y refinancia automáticamente a los clientes con DTI > 50% añadiendo 12 meses
al plazo hasta que el DTI sea <= 50%.

Sistema de amortización francés:
    Cuota = C * r / (1 - (1 + r)^(-n))
donde:
    C = capital pendiente
    r = tipo de interés mensual (interes_anual / 100 / 12)
    n = plazo en meses
"""

import csv
import json
import os

# ---------------------------------------------------------------------------
# Rutas de los ficheros (relativas al directorio del script)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENTES_CSV = os.path.join(BASE_DIR, "clientes.csv")
PRESTAMOS_JSON = os.path.join(BASE_DIR, "prestamos.json")


def cargar_clientes(ruta_csv):
    """Lee clientes.csv y devuelve un dict {id_cliente: {nombre, salario_neto}}."""
    clientes = {}
    with open(ruta_csv, newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            id_cliente = int(fila["id_cliente"])
            clientes[id_cliente] = {
                "nombre": fila["nombre"],
                "salario_neto": float(fila["salario_neto"]),
            }
    return clientes


def cargar_prestamos(ruta_json):
    """Lee prestamos.json y devuelve una lista de dicts."""
    with open(ruta_json, encoding="utf-8") as f:
        return json.load(f)


def calcular_cuota_francesa(capital, interes_anual, plazo_meses):
    """Calcula la cuota mensual con el sistema de amortización francés."""
    r = interes_anual / 100.0 / 12.0  # tipo mensual
    if r == 0:
        return capital / plazo_meses
    return capital * r / (1 - (1 + r) ** (-plazo_meses))


def calcular_dti(cuota_mensual, salario_neto):
    """Devuelve el ratio Debt-To-Income (cuota / salario)."""
    if salario_neto == 0:
        return float("inf")
    return cuota_mensual / salario_neto


def procesar_clientes():
    """Proceso principal: cruza datos, calcula DTI y refinancia si es necesario."""
    clientes = cargar_clientes(CLIENTES_CSV)
    prestamos = cargar_prestamos(PRESTAMOS_JSON)

    resultados = []

    for prestamo in prestamos:
        id_cliente = prestamo["id_cliente"]
        capital = prestamo["capital_pendiente"]
        interes = prestamo["interes_anual"]
        plazo = prestamo["plazo_meses"]

        cliente = clientes.get(id_cliente)
        if cliente is None:
            print(f"[AVISO] Cliente {id_cliente} no encontrado en clientes.csv. Se omite.")
            continue

        nombre = cliente["nombre"]
        salario = cliente["salario_neto"]

        cuota = calcular_cuota_francesa(capital, interes, plazo)
        dti = calcular_dti(cuota, salario)

        estado = "OK"
        plazo_original = plazo

        # ----- Bucle de refinanciación -----
        if dti > 0.50:
            # Comprobar si es matemáticamente posible refinanciar.
            # La cuota mínima teórica (plazo → ∞) es el pago de solo intereses:
            #   cuota_minima = capital * r
            # Si esa cuota mínima ya supera el umbral DTI, no hay plazo
            # que pueda resolver el problema.
            r_mensual = interes / 100.0 / 12.0
            cuota_minima_teorica = capital * r_mensual if r_mensual > 0 else 0
            dti_minimo_teorico = calcular_dti(cuota_minima_teorica, salario)

            if dti_minimo_teorico > 0.50:
                # Imposible reducir DTI por debajo del 50% solo con
                # ampliación de plazo → marcar como No Refinanciable.
                estado = "No Refinanciable"
                print(
                    f"[INFO] Cliente {id_cliente} ({nombre}): DTI mínimo teórico "
                    f"= {dti_minimo_teorico:.2%}. Refinanciación imposible solo "
                    f"con ampliación de plazo."
                )
            else:
                MAX_PLAZO_MESES = 12000  # límite de seguridad (1000 años)
                while dti > 0.50 and plazo < MAX_PLAZO_MESES:
                    plazo += 12  # añadir 12 meses al plazo
                    cuota = calcular_cuota_francesa(capital, interes, plazo)
                    dti = calcular_dti(cuota, salario)
                estado = "Refinanciado"

        resultados.append({
            "id_cliente": id_cliente,
            "nombre": nombre,
            "salario_neto": salario,
            "capital_pendiente": capital,
            "interes_anual": interes,
            "plazo_original": plazo_original,
            "plazo_final": plazo,
            "cuota_mensual": round(cuota, 2),
            "dti": round(dti, 4),
            "estado": estado,
        })

    return resultados


def imprimir_resultados(resultados):
    """Muestra los resultados de forma tabular por consola."""
    sep = "-" * 120
    print(sep)
    print(
        f"{'ID':>4} | {'Nombre':<22} | {'Salario':>10} | {'Capital':>12} | "
        f"{'Interés':>8} | {'Plazo Orig':>10} | {'Plazo Final':>11} | "
        f"{'Cuota':>10} | {'DTI':>8} | {'Estado'}"
    )
    print(sep)
    for r in resultados:
        print(
            f"{r['id_cliente']:>4} | {r['nombre']:<22} | "
            f"{r['salario_neto']:>10.2f} | {r['capital_pendiente']:>12.2f} | "
            f"{r['interes_anual']:>7.2f}% | {r['plazo_original']:>10} | "
            f"{r['plazo_final']:>11} | {r['cuota_mensual']:>10.2f} | "
            f"{r['dti']:>7.2%} | {r['estado']}"
        )
    print(sep)


if __name__ == "__main__":
    print("=== Política de Reestructuración de Deuda ===\n")
    resultados = procesar_clientes()
    imprimir_resultados(resultados)
    print(f"\nTotal clientes procesados: {len(resultados)}")
    refinanciados = sum(1 for r in resultados if r["estado"] == "Refinanciado")
    no_refinanciables = sum(1 for r in resultados if r["estado"] == "No Refinanciable")
    ok = sum(1 for r in resultados if r["estado"] == "OK")
    print(f"Clientes OK:               {ok}")
    print(f"Clientes refinanciados:    {refinanciados}")
    print(f"Clientes no refinanciables:{no_refinanciables}")
