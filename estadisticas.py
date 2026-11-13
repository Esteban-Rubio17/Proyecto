"""Métricas estadísticas descriptivas y correlaciones (NumPy + Pandas).

Trabaja sobre la tabla mensual (departamento x año x mes) generada por limpieza.py.
Uso independiente:  python estadisticas.py
"""
import numpy as np
import pandas as pd

VARIABLES_AMBIENTALES = ["temp_media", "lluvia_mm", "humedad"]


def pearson(x, y):
    """Correlación de Pearson ignorando NaN. Devuelve NaN si no es calculable."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    valido = np.isfinite(x) & np.isfinite(y)
    if valido.sum() < 3 or np.std(x[valido]) == 0 or np.std(y[valido]) == 0:
        return np.nan
    return float(np.corrcoef(x[valido], y[valido])[0, 1])


def spearman(x, y):
    """Correlación de Spearman (Pearson sobre rangos); robusta a valores extremos."""
    x, y = pd.Series(x, dtype=float), pd.Series(y, dtype=float)
    valido = x.notna() & y.notna()
    return pearson(x[valido].rank().to_numpy(), y[valido].rank().to_numpy())


def descriptiva(mensual, col="casos_total"):
    """Calcula las métricas descriptivas clave de los casos mensuales por departamento.

    Devuelve un diccionario con: media, desviación estándar, coeficiente de variación,
    máximo (y dónde ocurrió), mínimo, percentiles 25/50/75/90/95, total de casos y
    porcentaje de meses sin casos.
    """
    x = mensual[col].to_numpy(dtype=float)
    pico = mensual.loc[mensual[col].idxmax()]
    p25, p50, p75, p90, p95 = np.percentile(x, [25, 50, 75, 90, 95])
    media, desv = float(np.mean(x)), float(np.std(x, ddof=1))
    return {
        "total_casos": float(np.sum(x)),
        "media": media,
        "desviacion_estandar": desv,
        "coef_variacion_pct": desv / media * 100 if media else np.nan,
        "maximo": float(np.max(x)),
        "maximo_donde": f"{pico['departamento']} ({int(pico['mes']):02d}/{int(pico['anio'])})",
        "minimo": float(np.min(x)),
        "p25": float(p25), "mediana": float(p50), "p75": float(p75),
        "p90": float(p90), "p95": float(p95),
        "pct_meses_sin_casos": float(np.mean(x == 0) * 100),
    }


def tabla_metricas(mensual, col="casos_total"):
    """Devuelve las métricas de `descriptiva` como tabla legible (Métrica, Valor)."""
    m = descriptiva(mensual, col)
    filas = [
        ("Total de casos", f"{m['total_casos']:,.0f}"),
        ("Media mensual por departamento", f"{m['media']:,.1f}"),
        ("Desviación estándar", f"{m['desviacion_estandar']:,.1f}"),
        ("Coeficiente de variación", f"{m['coef_variacion_pct']:,.0f} %"),
        ("Máximo mensual", f"{m['maximo']:,.0f}  ·  {m['maximo_donde']}"),
        ("Mínimo mensual", f"{m['minimo']:,.0f}"),
        ("Mediana (P50)", f"{m['mediana']:,.1f}"),
        ("Percentil 90", f"{m['p90']:,.1f}"),
        ("Percentil 95", f"{m['p95']:,.1f}"),
        ("Meses-departamento sin casos", f"{m['pct_meses_sin_casos']:,.1f} %"),
    ]
    return pd.DataFrame(filas, columns=["Métrica", "Valor"])


def ranking_departamentos(mensual, col="casos_total"):
    """Resumen por departamento: total, media, desviación, CV y mes de mayor actividad."""
    g = mensual.groupby("departamento")[col]
    resumen = pd.DataFrame({"total": g.sum(), "media_mensual": g.mean(),
                            "desviacion": g.std(ddof=1), "maximo": g.max()})
    resumen["cv_pct"] = resumen["desviacion"] / resumen["media_mensual"].replace(0, np.nan) * 100
    mes_pico = (mensual.groupby(["departamento", "mes"])[col].mean().unstack()
                .idxmax(axis=1).rename("mes_pico"))
    resumen = resumen.join(mes_pico)
    resumen["participacion_pct"] = resumen["total"] / resumen["total"].sum() * 100
    return resumen.sort_values("total", ascending=False)


def estacionalidad(mensual, col="casos_total"):
    """Casos promedio por mes calendario e índice estacional (1.0 = promedio anual)."""
    por_mes = mensual.groupby("mes")[col].mean()
    media = por_mes.mean()
    return pd.DataFrame({"promedio": por_mes,
                         "indice": por_mes / media if media else np.nan}).reset_index()


def _z_por_departamento(df, columna):
    """Estandariza (z-score) una columna dentro de cada departamento."""
    def z(s):
        desv = s.std(ddof=0)
        return (s - s.mean()) / desv if desv and not np.isnan(desv) else s * np.nan
    return df.groupby("cod_dpto")[columna].transform(z)


def correlacion_con_rezagos(mensual, variables=VARIABLES_AMBIENTALES,
                            col="casos_total", max_rezago=3):
    """Correlación entre el clima de hace `r` meses y los casos del mes actual.

    Se estandariza dentro de cada departamento para medir cómo se mueven juntos en el
    tiempo, sin que las diferencias estructurales entre departamentos (p. ej. uno
    caliente y poblado vs. uno frío) inflen la correlación.
    """
    df = mensual.sort_values(["cod_dpto", "fecha"]).copy()
    df["_casos"] = np.log1p(df[col])
    df["_casos_z"] = _z_por_departamento(df, "_casos")
    filas = []
    for variable in variables:
        df["_var_z"] = _z_por_departamento(df, variable)
        for rezago in range(max_rezago + 1):
            x = df.groupby("cod_dpto")["_var_z"].shift(rezago)
            filas.append({"variable": variable, "rezago_meses": rezago,
                          "pearson": pearson(x, df["_casos_z"]),
                          "spearman": spearman(x, df["_casos_z"])})
    return pd.DataFrame(filas)


def relacion_geografica(mensual, col="casos_total"):
    """Relaciona el clima promedio de cada departamento con su nivel de casos.

    Devuelve (tabla por departamento, diccionario de correlaciones de Spearman).
    """
    tabla = (mensual.groupby("departamento")
             .agg(temp_media=("temp_media", "mean"), lluvia_mm=("lluvia_mm", "mean"),
                  humedad=("humedad", "mean"), casos=(col, "sum"))
             .reset_index())
    correlaciones = {v: spearman(tabla[v], tabla["casos"]) for v in VARIABLES_AMBIENTALES}
    return tabla, correlaciones


def describir_correlacion(r):
    """Traduce un coeficiente de correlación a texto (fuerza y dirección)."""
    if r is None or np.isnan(r):
        return "no calculable"
    fuerza = ("prácticamente nula" if abs(r) < 0.1 else "débil" if abs(r) < 0.3
              else "moderada" if abs(r) < 0.5 else "fuerte")
    if fuerza == "prácticamente nula":
        return fuerza
    return f"{fuerza} y {'positiva' if r > 0 else 'negativa'}"


if __name__ == "__main__":
    datos = pd.read_csv("data/processed/dengue_mensual.csv", dtype={"cod_dpto": str},
                        parse_dates=["fecha"])
    print(tabla_metricas(datos).to_string(index=False))
    print("\nTop 5 departamentos:\n", ranking_departamentos(datos).head(5).round(1))
    print("\nEstacionalidad:\n", estacionalidad(datos).round(2))
    print("\nCorrelación con rezagos:\n", correlacion_con_rezagos(datos).round(3))
    print("\nRelación geográfica:", relacion_geografica(datos)[1])
