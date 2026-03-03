"""
Script de cálculo de exposición total de riesgo para cartera de clientes
de banca de empresas.

Regla de negocio:
  La exposición total de una empresa = su propia deuda
  + calcular_exposicion_total(id_matriz).
  Si id_matriz es nulo o vacío, devuelve solo su propia deuda.

El sistema asume que el JSON ha sido validado previamente por Compliance
y representa un árbol jerárquico perfecto sin referencias circulares.
"""

import json
from typing import Dict


def cargar_empresas(ruta: str) -> Dict[str, dict]:
    """Carga el archivo JSON y devuelve un diccionario indexado por id."""
    with open(ruta, "r", encoding="utf-8") as f:
        lista = json.load(f)
    return {empresa["id"]: empresa for empresa in lista}


def calcular_exposicion_total(id_empresa: str, empresas: Dict[str, dict]) -> int:
    """
    Calcula recursivamente la exposición total de riesgo de una empresa.

    Parámetros:
        id_empresa: Identificador de la empresa.
        empresas:   Diccionario de empresas indexado por id.

    Retorna:
        La suma acumulada de deuda propia + exposición de la empresa matriz.
    """
    if id_empresa not in empresas:
        return 0

    empresa = empresas[id_empresa]
    deuda_propia: int = empresa["deuda"]

    id_matriz: str = empresa.get("id_matriz", "") or ""

    if not id_matriz:
        return deuda_propia

    return deuda_propia + calcular_exposicion_total(id_matriz, empresas)


def main() -> None:
    empresas = cargar_empresas("empresas.json")

    print("=" * 55)
    print("  CÁLCULO DE EXPOSICIÓN TOTAL DE RIESGO CORPORATIVO")
    print("=" * 55)

    for id_empresa in empresas:
        exposicion = calcular_exposicion_total(id_empresa, empresas)  # noqa: E501
        print(
            f"\n  Empresa {id_empresa}: "
            f"exposición total = {exposicion:,}"
        )

    print("\n" + "=" * 55)


if __name__ == "__main__":
    main()
