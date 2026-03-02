import csv
import json
import random

random.seed(42)

# --- clientes.csv ---
clientes = []
for i in range(1, 101):
    clientes.append({"id_cliente": i, "salario_neto": round(random.uniform(1500, 5000), 2)})

with open("clientes.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["id_cliente", "salario_neto"])
    writer.writeheader()
    writer.writerows(clientes)

# --- prestamos.json ---
prestamos = []
for c in clientes:
    capital = round(random.uniform(5000, 200000), 2)
    interes = round(random.uniform(3, 7), 2)
    n = 240  # plazo 20 años
    r = interes / 100 / 12
    cuota = round(capital * r / (1 - (1 + r) ** -n), 2)
    prestamos.append({
        "id_cliente": c["id_cliente"],
        "capital_pendiente": capital,
        "interes_anual": interes,
        "cuota_mensual": cuota,
    })

with open("prestamos.json", "w") as f:
    json.dump(prestamos, f, indent=2)

print("clientes.csv y prestamos.json generados.")
