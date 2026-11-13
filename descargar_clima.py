"""Descarga clima diario 2020-2025 de NASA POWER para la capital de cada departamento.

Uso:  python descargar_clima.py      (tarda unos minutos; requiere internet)
Salida: data/raw/clima_diario_2020_2025.csv
"""
import time

import pandas as pd
import requests

from config import ARCHIVO_CLIMA, DEPARTAMENTOS

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
VARIABLES = "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M"


def descargar_punto(lat, lon, inicio="20200101", fin="20251231", reintentos=3):
    """Descarga el clima diario de un punto. Devuelve un DataFrame (fecha + variables)."""
    params = {"parameters": VARIABLES, "community": "AG", "latitude": lat,
              "longitude": lon, "start": inicio, "end": fin, "format": "JSON"}
    for intento in range(1, reintentos + 1):
        try:
            r = requests.get(URL, params=params, timeout=120)
            r.raise_for_status()
            datos = r.json()["properties"]["parameter"]  # {variable: {YYYYMMDD: valor}}
            df = pd.DataFrame(datos)
            df.index.name = "fecha"
            df = df.reset_index()
            df["fecha"] = pd.to_datetime(df["fecha"], format="%Y%m%d")
            variables = [c for c in df.columns if c != "fecha"]
            df[variables] = df[variables].apply(pd.to_numeric, errors="coerce")
            df[variables] = df[variables].mask(df[variables] == -999)  # -999 = sin dato
            return df
        except (requests.RequestException, KeyError, ValueError) as error:
            print(f"  intento {intento}/{reintentos} falló: {error}")
            time.sleep(5 * intento)
    raise RuntimeError(f"No se pudo descargar el punto ({lat}, {lon})")


def main():
    """Recorre los departamentos y guarda un único CSV con todo el clima diario."""
    tablas = []
    for codigo, (nombre, lat, lon) in DEPARTAMENTOS.items():
        print(f"Descargando {nombre}…")
        tabla = descargar_punto(lat, lon)
        tabla["cod_dpto"] = codigo
        tabla["departamento_clima"] = nombre
        tablas.append(tabla)
        time.sleep(1)  # no saturar la API
    ARCHIVO_CLIMA.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(tablas, ignore_index=True).to_csv(ARCHIVO_CLIMA, index=False)
    print(f"Guardado: {ARCHIVO_CLIMA}")


if __name__ == "__main__":
    main()
