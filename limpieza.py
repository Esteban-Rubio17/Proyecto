"""Pipeline de carga, limpieza y estructuración de datos de dengue (SIVIGILA) + clima.

Uso:  python limpieza.py
Entradas : data/raw/*.csv|xlsx (SIVIGILA 2020-2025), data/raw/clima_diario_2020_2025.csv,
           data/raw/poblacion_dane.csv (opcional)
Salidas  : data/processed/*.csv (listos para el dashboard)
"""
import logging
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from config import (AJUSTES_DESCARTADOS, ALIAS_COLUMNAS, ANIO_FIN, ANIO_INICIO,
                    ARCHIVO_CLIMA, ARCHIVO_POBLACION, CODIGO_COLOMBIA,
                    COLUMNAS_OBLIGATORIAS, CONDICION_MUERTO, DEPARTAMENTOS, EVENTOS,
                    FACTOR_EDAD_A_ANIOS, RUTA_PROCESADOS, RUTA_RAW)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

LLAVE_MES = ["cod_dpto", "anio", "mes"]
CONTEOS = ["casos_dengue", "muertes"]


# ----------------------------------------------------------------------------
# 1. Utilidades de texto y lectura
# ----------------------------------------------------------------------------
def normalizar_texto(texto):
    """Devuelve el texto en MAYÚSCULAS, sin tildes y sin espacios sobrantes.

    Sirve para unificar nombres inconsistentes (p. ej. 'Bogotá ', 'BOGOTA').
    Los valores nulos se devuelven como NaN.
    """
    if pd.isna(texto):
        return np.nan
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().upper()


def normalizar_nombre_columna(nombre):
    """Convierte 'COD_DPTO_O' / 'Año' en 'cod_dpto_o' / 'ano' (sin guion bajo final)."""
    n = normalizar_texto(nombre).lower()
    return re.sub(r"[^a-z0-9]+", "_", n).strip("_")


def leer_archivo(ruta):
    """Lee un CSV o Excel como texto, probando codificaciones y separadores comunes."""
    ruta = Path(ruta)
    if ruta.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(ruta, dtype=str)
    ultimo_error = None
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(ruta, sep=None, engine="python", dtype=str,
                               encoding=codificacion)
        except UnicodeDecodeError as error:
            ultimo_error = error
    raise ValueError(f"No se pudo leer {ruta.name}: {ultimo_error}")


def estandarizar_columnas(df):
    df = df.copy()
    df.columns = [normalizar_nombre_columna(c) for c in df.columns]
    renombrar = {}
    for canonico, alias in ALIAS_COLUMNAS.items():
        for a in alias:
            if a in df.columns:
                renombrar[a] = canonico
                break
    return df.rename(columns=renombrar)


# ----------------------------------------------------------------------------
# 2. Carga
# ----------------------------------------------------------------------------
def cargar_sivigila(carpeta=RUTA_RAW):
    excluir = ("clima", "poblacion")
    archivos = sorted(p for p in Path(carpeta).glob("*")
                      if p.suffix.lower() in {".csv", ".xlsx", ".xls"}
                      and not any(x in p.name.lower() for x in excluir))
    if not archivos:
        raise FileNotFoundError(f"No hay archivos SIVIGILA en {carpeta}")

    partes = []
    for ruta in archivos:
        crudo = leer_archivo(ruta)
        n_original = len(crudo)
        crudo = crudo.drop_duplicates()
        df = estandarizar_columnas(crudo)
        faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in df.columns]
        if faltan:
            raise ValueError(f"{ruta.name}: faltan columnas {faltan}. "
                             f"Disponibles: {list(df.columns)}. Agrega alias en config.py")
        for columna in ALIAS_COLUMNAS:           # columnas opcionales ausentes -> NaN
            if columna not in df.columns:
                df[columna] = np.nan
        df = df[list(ALIAS_COLUMNAS)].copy()     # descarta todas las demás columnas
        df["archivo_origen"] = ruta.name
        log.info("%s: %d filas (%d duplicados exactos eliminados)",
                 ruta.name, len(df), n_original - len(df))
        partes.append(df)
    return pd.concat(partes, ignore_index=True)


# ----------------------------------------------------------------------------
# 3. Limpieza por pasos
# ----------------------------------------------------------------------------
def asignar_tipo_evento(df):
    """Crea 'tipo_evento' (Dengue) y descarta otros eventos (p. ej. mortalidad)."""
    df = df.copy()
    if df["cod_evento"].notna().any():
        df["tipo_evento"] = pd.to_numeric(df["cod_evento"], errors="coerce").map(EVENTOS)
    elif df["nom_evento"].notna().any():
        nombre = df["nom_evento"].map(normalizar_texto).fillna("")
        tipo = pd.Series(np.nan, index=df.index, dtype="object")
        tipo[nombre.str.contains("DENGUE")] = "Dengue"
        tipo[nombre.str.contains("GRAVE")] = "Dengue grave"
        tipo[nombre.str.contains("MORTALIDAD")] = np.nan
        df["tipo_evento"] = tipo
    else:
        log.warning("Sin código ni nombre de evento: se asume que todo es 'Dengue'.")
        df["tipo_evento"] = "Dengue"
    return df.dropna(subset=["tipo_evento"])


def descartar_casos_invalidos(df):
    """Elimina casos descartados/mal digitados (campo AJUSTE) y casos fuera de Colombia."""
    ajuste = (df["ajuste"].astype("string").str.strip().str.upper()
              .str.replace(r"\.0$", "", regex=True))
    df = df[~ajuste.isin(AJUSTES_DESCARTADOS).fillna(False)]
    pais = pd.to_numeric(df["pais"], errors="coerce")
    return df[pais.isna() | (pais == CODIGO_COLOMBIA)]


def parsear_fechas(serie):
    """Convierte a datetime aceptando formato ISO (2021-03-15) o día/mes/año (15/03/2021)."""
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie
    fechas = pd.to_datetime(serie, errors="coerce", format="ISO8601")
    pendientes = fechas.isna() & serie.notna()
    if pendientes.any():
        fechas[pendientes] = pd.to_datetime(serie[pendientes], errors="coerce",
                                            dayfirst=True)
    return fechas


def normalizar_codigos(df):
    """Estandariza códigos DIVIPOLA: departamento de 2 dígitos y municipio de 5 dígitos."""
    df = df.copy()
    dpto = pd.to_numeric(df["cod_dpto"], errors="coerce")
    df = df[dpto.notna()].copy()
    dpto = dpto.loc[df.index].astype(int)
    df["cod_dpto"] = dpto.astype(str).str.zfill(2)

    mun = pd.to_numeric(df["cod_mun"], errors="coerce")
    mun = mun.where(mun >= 1000, dpto * 1000 + mun)
    df["cod_mun"] = mun.round().astype("Int64").astype(str).str.zfill(5)
    df.loc[mun.isna(), "cod_mun"] = np.nan
    return df[df["cod_dpto"].isin(DEPARTAMENTOS)]


def unificar_nombres(df):
    """Asigna nombre oficial de departamento y un único nombre por código de municipio."""
    df = df.copy()
    df["departamento"] = df["cod_dpto"].map({k: v[0] for k, v in DEPARTAMENTOS.items()})
    nombres = df["municipio"].map(normalizar_texto)
    moda = (pd.DataFrame({"cod_mun": df["cod_mun"], "m": nombres}).dropna()
            .groupby("cod_mun")["m"].agg(lambda s: s.mode().iat[0]))
    nombre_final = df["cod_mun"].map(moda).fillna(nombres)
    titulo = nombre_final.map(lambda s: s.title() if isinstance(s, str) else np.nan)
    df["municipio"] = titulo.where(titulo.notna(), "Municipio " + df["cod_mun"].astype(str))
    return df


def estandarizar_demografia(df):
    """Crea edad en años, grupo etario, sexo legible, área legible."""
    df = df.copy()
    edad = pd.to_numeric(df["edad"], errors="coerce")
    unidad = pd.to_numeric(df["unidad_edad"], errors="coerce").map(FACTOR_EDAD_A_ANIOS)
    edad_anios = edad * unidad.fillna(1.0)
    df["edad_anios"] = edad_anios.where((edad_anios >= 0) & (edad_anios <= 110))

    etiquetas = ["0-4", "5-14", "15-29", "30-44", "45-59", "60+"]
    grupo = pd.cut(df["edad_anios"], bins=[0, 5, 15, 30, 45, 60, 111],
                   labels=etiquetas, right=False)
    df["grupo_edad"] = grupo.astype("object").fillna("Sin dato")

    sexo = df["sexo"].map(normalizar_texto)
    df["sexo"] = sexo.map({"M": "Masculino", "F": "Femenino"}).fillna("No reportado")

    area = pd.to_numeric(df["area"], errors="coerce")
    df["area"] = area.map({1: "Cabecera", 2: "Centro poblado", 3: "Rural disperso"}) \
        .fillna("Sin dato")

    df["fallecido"] = pd.to_numeric(df["condicion_final"], errors="coerce") == CONDICION_MUERTO
    return df


def limpiar_sivigila(df):
    """Aplica todos los pasos de limpieza. Devuelve (DataFrame limpio, auditoría)."""
    auditoria = [{"paso": "Filas cargadas (sin duplicados exactos)", "filas": len(df)}]

    def registrar(paso, datos):
        auditoria.append({"paso": paso, "filas": len(datos)})
        return datos

    df = registrar("Solo eventos dengue / dengue grave", asignar_tipo_evento(df))
    df = registrar("Sin casos descartados ni fuera de Colombia", descartar_casos_invalidos(df))

    anio_epi = pd.to_numeric(df["anio"], errors="coerce")
    df = df.assign(fecha=parsear_fechas(df["fecha"]))
    df = registrar("Con fecha de notificación válida", df.dropna(subset=["fecha"]))
    df = df.assign(anio_epi=anio_epi.loc[df.index].fillna(df["fecha"].dt.year).astype(int),
                   anio=df["fecha"].dt.year, mes=df["fecha"].dt.month)
    semana = pd.to_numeric(df["semana"], errors="coerce")
    semana = semana.fillna(df["fecha"].dt.isocalendar().week.astype(float))
    df["semana"] = semana.clip(1, 53).astype(int)
    df = registrar(f"Años {ANIO_INICIO}-{ANIO_FIN}", df[df["anio"].between(ANIO_INICIO, ANIO_FIN)])

    df = registrar("Código de departamento válido", normalizar_codigos(df))
    df = unificar_nombres(df)
    df = estandarizar_demografia(df)

    columnas = ["fecha", "anio", "mes", "anio_epi", "semana", "cod_dpto", "departamento",
                "cod_mun", "municipio", "area", "sexo", "edad_anios", "grupo_edad",
                "tipo_evento", "fallecido"]
    return df[columnas].reset_index(drop=True), pd.DataFrame(auditoria)


# ----------------------------------------------------------------------------
# 4. Agregación, clima y unión
# ----------------------------------------------------------------------------
def contar_casos(df, claves):
    """Cuenta casos por `claves` separando dengue, dengue grave, total y muertes."""
    g = df.groupby(claves + ["tipo_evento"]).size().unstack("tipo_evento", fill_value=0)
    g.columns.name = None
    g = g.rename(columns={"Dengue": "casos_dengue", "Dengue grave": "casos_grave"})
    for c in ("casos_dengue", "casos_grave"):
        if c not in g.columns:
            g[c] = 0
    g["casos_total"] = g["casos_dengue"] + g["casos_grave"]
    muertes = df[df["fallecido"]].groupby(claves).size().rename("muertes")
    g = g.join(muertes)
    g["muertes"] = g["muertes"].fillna(0)
    g = g.reset_index()
    g[CONTEOS] = g[CONTEOS].astype(int)
    return g[claves + CONTEOS]


def construir_tablas(df):
    """Genera las tablas agregadas que consume el dashboard."""
    semanal_base = df[df["anio_epi"].between(ANIO_INICIO, ANIO_FIN)]
    semanal = contar_casos(semanal_base, ["cod_dpto", "anio_epi", "semana"])
    return {
        "mensual": contar_casos(df, LLAVE_MES),
        "semanal": semanal.rename(columns={"anio_epi": "anio"}),
        "municipios": contar_casos(df, ["cod_dpto", "cod_mun", "municipio", "anio"]),
        "perfil": contar_casos(df, ["cod_dpto", "anio", "sexo", "grupo_edad", "area"]),
    }


def procesar_clima(ruta=ARCHIVO_CLIMA):
    """Convierte el clima diario (NASA POWER) a mensual por departamento.

    Temperaturas y humedad: promedio mensual. Precipitación: suma mensual.
    """
    clima = pd.read_csv(ruta, dtype={"cod_dpto": str}, parse_dates=["fecha"])
    clima["cod_dpto"] = clima["cod_dpto"].str.zfill(2)
    for c in ("T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M"):
        clima[c] = pd.to_numeric(clima[c], errors="coerce")
    clima["anio"] = clima["fecha"].dt.year
    clima["mes"] = clima["fecha"].dt.month
    return (clima.groupby(LLAVE_MES)
            .agg(temp_media=("T2M", "mean"), temp_max=("T2M_MAX", "mean"),
                 temp_min=("T2M_MIN", "mean"),
                 lluvia_mm=("PRECTOTCORR", lambda s: s.sum(min_count=1)),
                 humedad=("RH2M", "mean"))
            .reset_index())


def unir_dengue_clima(casos_mes, clima_mes):
    """Une casos y clima por departamento-año-mes usando una rejilla completa.

    La rejilla garantiza que los meses sin casos aparezcan con 0 (y no desaparezcan).
    """
    rejilla = pd.MultiIndex.from_product(
        [sorted(clima_mes["cod_dpto"].unique()), range(ANIO_INICIO, ANIO_FIN + 1), range(1, 13)],
        names=LLAVE_MES).to_frame(index=False)
    final = (rejilla.merge(casos_mes, on=LLAVE_MES, how="left")
             .merge(clima_mes, on=LLAVE_MES, how="left", validate="one_to_one"))
    final[CONTEOS] = final[CONTEOS].fillna(0).astype(int)
    final["departamento"] = final["cod_dpto"].map({k: v[0] for k, v in DEPARTAMENTOS.items()})
    final["fecha"] = pd.to_datetime(dict(year=final["anio"], month=final["mes"], day=1))
    return final


def agregar_poblacion(mensual, ruta=ARCHIVO_POBLACION):
    """Agrega población (DANE) e incidencia por 100.000 hab. Si no hay archivo, deja NaN."""
    mensual = mensual.copy()
    if not Path(ruta).exists():
        log.warning("No existe %s: se omite la incidencia (el dashboard usará casos).", ruta)
        mensual["poblacion"] = np.nan
    else:
        pob = pd.read_csv(ruta, dtype={"cod_dpto": str})
        pob["cod_dpto"] = pob["cod_dpto"].str.zfill(2)
        mensual = mensual.merge(pob[["cod_dpto", "anio", "poblacion"]],
                                on=["cod_dpto", "anio"], how="left")
    mensual["incidencia_100k"] = mensual["casos_total"] / mensual["poblacion"] * 100_000
    return mensual


# ----------------------------------------------------------------------------
# 5. Programa principal
# ----------------------------------------------------------------------------
def main():
    """Ejecuta el pipeline completo y exporta los CSV procesados."""
    RUTA_PROCESADOS.mkdir(parents=True, exist_ok=True)
    limpio, auditoria = limpiar_sivigila(cargar_sivigila())
    tablas = construir_tablas(limpio)
    mensual = unir_dengue_clima(tablas["mensual"], procesar_clima())
    tablas["mensual"] = agregar_poblacion(mensual)

    for nombre, tabla in tablas.items():
        tabla.to_csv(RUTA_PROCESADOS / f"dengue_{nombre}.csv", index=False)
        log.info("dengue_%s.csv -> %d filas", nombre, len(tabla))
    auditoria.to_csv(RUTA_PROCESADOS / "auditoria_limpieza.csv", index=False)
    print(auditoria.to_string(index=False))


if __name__ == "__main__":
    main()
