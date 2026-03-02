import pandas as pd

clientes = pd.read_csv("clientes.csv")
prestamos = pd.read_json("prestamos.json")

df = clientes.merge(prestamos, on="id_cliente")
df["dti"] = df["cuota_mensual"] / df["salario_neto"]
df["clasificacion"] = df["dti"].apply(lambda x: "Watchlist" if x > 0.40 else "Performing")

df.to_csv("scoring_mensual.csv", index=False)
print("scoring_mensual.csv generado.")
