"""Dashboard: factores geográficos, temporales y ambientales del dengue en Colombia (2020-2025).

Ejecutar:  streamlit run app.py
Requiere los CSV de data/processed (se generan con `python limpieza.py`).
"""
import math

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import estadisticas as est
from config import ANIO_FIN, ANIO_INICIO, DEPARTAMENTOS, RUTA_PROCESADOS

st.set_page_config(page_title="Dengue en Colombia 2020-2025", page_icon="🦟", layout="wide")

COLUMNA_TIPO = {"Todos": "casos_total", "Dengue": "casos_dengue"}
AMBIENTALES = {"Temperatura media (°C)": "temp_media",
               "Lluvia acumulada (mm/mes)": "lluvia_mm",
               "Humedad relativa (%)": "humedad"}
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
ORDEN_EDAD = ["0-4", "5-14", "15-29", "30-44", "45-59", "60+", "Sin dato"]
ARCHIVOS = {"mensual": "dengue_mensual.csv", "semanal": "dengue_semanal.csv",
            "municipios": "dengue_municipios.csv", "perfil": "dengue_perfil.csv"}
NOMBRES_DPTO = {codigo: datos[0] for codigo, datos in DEPARTAMENTOS.items()}



@st.cache_data(show_spinner="Cargando datos…")
def cargar_datos():
    """Lee los CSV procesados y agrega el nombre del departamento. None si faltan archivos."""
    if not all((RUTA_PROCESADOS / f).exists() for f in ARCHIVOS.values()):
        return None
    tipos = {"cod_dpto": str, "cod_mun": str}
    datos = {k: pd.read_csv(RUTA_PROCESADOS / f, dtype=tipos) for k, f in ARCHIVOS.items()}
    for tabla in datos.values():
        tabla["departamento"] = tabla["cod_dpto"].map(NOMBRES_DPTO)
    datos["mensual"]["fecha"] = pd.to_datetime(datos["mensual"]["fecha"])
    return datos


@st.cache_data
def agregar_por_departamento(mensual, col, incidencia):
    """Suma casos por departamento; si `incidencia`, suma las tasas anuales por 100.000 hab."""
    anual = mensual.groupby(["cod_dpto", "departamento", "anio"], as_index=False).agg(
        casos=(col, "sum"), poblacion=("poblacion", "first"))
    anual["valor"] = anual["casos"] / anual["poblacion"] * 100_000 if incidencia else anual["casos"]
    agg = anual.groupby(["cod_dpto", "departamento"], as_index=False).agg(
        valor=("valor", "sum"), casos=("casos", "sum"))
    coords = pd.DataFrame([(c, d[1], d[2]) for c, d in DEPARTAMENTOS.items()],
                          columns=["cod_dpto", "lat", "lon"])
    return agg.merge(coords, on="cod_dpto")


@st.cache_data
def calcular_rezagos(mensual, col):
    """Correlaciones clima-casos con rezagos de 0 a 3 meses (con nombres legibles)."""
    rez = est.correlacion_con_rezagos(mensual, col=col)
    rez["variable"] = rez["variable"].map({v: k for k, v in AMBIENTALES.items()})
    return rez


def filtrar(df, deptos, anios):
    """Filtra una tabla por departamentos seleccionados y rango de años."""
    return df[df["departamento"].isin(deptos) & df["anio"].between(*anios)]

#mapas
def figura_mapa(agg, etiqueta):
    """Mapa de burbujas por departamento (tamaño y color según la métrica elegida)."""
    agg = agg.assign(tam=agg["valor"].clip(lower=0).fillna(0) + 1)
    opciones = dict(lat="lat", lon="lon", size="tam", color="valor", hover_name="departamento",
                    hover_data={"valor": ":,.1f", "lat": False, "lon": False, "tam": False},
                    color_continuous_scale="YlOrRd", size_max=45, zoom=4.2,
                    center={"lat": 4.5, "lon": -73.5}, height=520, labels={"valor": etiqueta})
    if hasattr(px, "scatter_map"):
        return px.scatter_map(agg, map_style="open-street-map", **opciones)
    return px.scatter_mapbox(agg, mapbox_style="open-street-map", **opciones)  


def figura_dispersion(datos, x, y, etiquetas, log_y=False, color=None, texto=None):
    """Dispersión con línea de tendencia (regresión lineal; en log si `log_y`)."""
    fig = px.scatter(datos, x=x, y=y, color=color, text=texto, labels=etiquetas,
                     hover_data=[c for c in ("departamento", "mes") if c in datos.columns],
                     opacity=0.6, log_y=log_y)
    xs = datos[x].to_numpy(dtype=float)
    ys = np.log1p(datos[y].to_numpy(dtype=float)) if log_y else datos[y].to_numpy(dtype=float)
    valido = np.isfinite(xs) & np.isfinite(ys)
    if valido.sum() > 2 and np.std(xs[valido]) > 0:
        pendiente, intercepto = np.polyfit(xs[valido], ys[valido], 1)
        rango = np.linspace(xs[valido].min(), xs[valido].max(), 50)
        recta = intercepto + pendiente * rango
        fig.add_trace(go.Scatter(x=rango, y=np.expm1(recta) if log_y else recta, mode="lines",
                                 name="Tendencia", line=dict(color="black", width=3)))
    if texto:
        fig.update_traces(textposition="top center", selector=dict(mode="markers+text"))
    return fig


# ---------------------------------------------------------------------------
# Pestañas
# ---------------------------------------------------------------------------
def pestana_intro(m, col):
    """Pregunta guía, hipótesis e indicadores clave de la selección actual."""
    st.subheader("Pregunta guía")
    st.markdown("**¿Qué factores geográficos, temporales y ambientales están relacionados con "
                "la incidencia del dengue en Colombia?**")
    st.markdown(
        "- **Geográficos:** ¿en qué departamentos y municipios se concentran los casos?\n"
        "- **Temporales:** ¿hay estacionalidad (meses o semanas epidemiológicas críticas) y "
        "años de brote?\n"
        "- **Ambientales:** ¿cómo se asocian la temperatura, la lluvia y la humedad con los casos, "
        "y con cuántos meses de rezago?")
    total = m[col].sum()
    pct_graves = m["casos_grave"].sum() / m["casos_total"].sum() * 100 if m["casos_total"].sum() else 0
    estac = est.estacionalidad(m, col)
    mes_pico = MESES[int(estac.loc[estac["indice"].idxmax(), "mes"]) - 1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Casos en la selección", f"{total:,.0f}")
    c2.metric("Mes con más casos (promedio)", mes_pico)
    c3.metric("% dengue grave", f"{pct_graves:.1f} %")
    c4.metric("Muertes notificadas", f"{m['muertes'].sum():,.0f}")
    st.caption("Fuentes: SIVIGILA (INS) 2020-2025 · clima: NASA POWER (capital de cada "
               "departamento), Use los filtros de la barra lateral.")


def pestana_espaciotemporal(m, datos, deptos, anios, col, usar_incidencia):
    """Mapa, ranking, series semanales, estacionalidad, municipios y perfil demográfico."""
    etiqueta = "Incidencia acumulada por 100.000 hab." if usar_incidencia else "Casos"
    agg = agregar_por_departamento(m, col, usar_incidencia)
    st.subheader("1. Dimensión geográfica")
    izq, der = st.columns([3, 2])
    with izq:
        st.plotly_chart(figura_mapa(agg, etiqueta), use_container_width=True)
    with der:
        top = agg.nlargest(15, "valor").sort_values("valor")
        fig = px.bar(top, x="valor", y="departamento", orientation="h",
                     labels={"valor": etiqueta, "departamento": ""},
                     title="Top 15 departamentos", color="valor",
                     color_continuous_scale="YlOrRd")
        fig.update_layout(coloraxis_showscale=False, height=520)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("2. Dimensión temporal")
    semanal = (filtrar(datos["semanal"], deptos, anios)
               .groupby(["anio", "semana"], as_index=False)[col].sum())
    semanal["anio"] = semanal["anio"].astype(str)
    fig = px.line(semanal, x="semana", y=col, color="anio",
                  labels={"semana": "Semana epidemiológica", col: "Casos", "anio": "Año"},
                  title="Casos por semana epidemiológica y año")
    st.plotly_chart(fig, use_container_width=True)

    izq, der = st.columns(2)
    with izq:
        pivote = (m.pivot_table(index="anio", columns="mes", values=col, aggfunc="sum")
                  .reindex(columns=range(1, 13)))
        fig = px.imshow(pivote.to_numpy(), x=MESES, y=pivote.index.astype(str), aspect="auto",
                        color_continuous_scale="YlOrRd", title="Estacionalidad: casos por mes y año",
                        labels={"x": "Mes", "y": "Año", "color": "Casos"})
        st.plotly_chart(fig, use_container_width=True)
    with der:
        mun = (filtrar(datos["municipios"], deptos, anios)
               .groupby(["municipio", "departamento"], as_index=False)[col].sum().nlargest(10, col))
        mun["etiqueta"] = mun["municipio"] + " (" + mun["departamento"] + ")"
        fig = px.bar(mun.sort_values(col), x=col, y="etiqueta", orientation="h",
                     labels={col: "Casos", "etiqueta": ""}, title="Top 10 municipios")
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Perfil demográfico de los casos (edad y sexo)"):
        perfil = filtrar(datos["perfil"], deptos, anios)
        por_edad = perfil.groupby(["grupo_edad", "sexo"], as_index=False)[col].sum()
        fig = px.bar(por_edad, x="grupo_edad", y=col, color="sexo", barmode="group",
                     category_orders={"grupo_edad": ORDEN_EDAD},
                     labels={"grupo_edad": "Grupo de edad (años)", col: "Casos"})
        st.plotly_chart(fig, use_container_width=True)


def pestana_ambiental(m, col, rango_temp):
    """Dispersión clima-casos, correlaciones con rezago y relación geográfica."""
    st.subheader("Relación entre clima y casos")
    c1, c2 = st.columns([2, 1])
    etiqueta_var = c1.selectbox("Variable ambiental", list(AMBIENTALES))
    escala_log = c2.checkbox("Escala logarítmica en casos", value=False,
                             help="Los meses con 0 casos no se dibujan en escala log.")
    variable = AMBIENTALES[etiqueta_var]
    mt = m[m["temp_media"].between(*rango_temp)].dropna(subset=[variable])
    if mt.empty:
        st.warning("No hay datos con los filtros actuales.")
        return

    r_p = est.pearson(mt[variable], mt[col])
    r_s = est.spearman(mt[variable], mt[col])
    k1, k2, k3 = st.columns(3)
    k1.metric("Observaciones (depto-mes)", f"{len(mt):,}")
    k2.metric("Pearson", f"{r_p:.2f}" if not np.isnan(r_p) else "—")
    k3.metric("Spearman", f"{r_s:.2f}" if not np.isnan(r_s) else "—")

    fig = figura_dispersion(mt.assign(anio_txt=mt["anio"].astype(str)), variable, col,
                            {variable: etiqueta_var, col: "Casos al mes", "anio_txt": "Año"},
                            log_y=escala_log, color="anio_txt")
    fig.update_layout(title=f"{etiqueta_var} vs. casos (cada punto = un departamento en un mes)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Esta correlación mezcla departamentos distintos; la gráfica de rezagos de abajo "
               "compara cada departamento consigo mismo en el tiempo.")

    izq, der = st.columns(2)
    with izq:
        rez = calcular_rezagos(m, col)
        fig = px.bar(rez, x="rezago_meses", y="spearman", color="variable", barmode="group",
                     labels={"rezago_meses": "Rezago del clima (meses)",
                             "spearman": "Correlación de Spearman", "variable": ""},
                     title="¿Con cuántos meses de rezago el clima se asocia a los casos?")
        st.plotly_chart(fig, use_container_width=True)
    with der:
        tabla_geo, corr_geo = est.relacion_geografica(m, col)
        fig = figura_dispersion(tabla_geo, variable, "casos",
                                {variable: f"{etiqueta_var} (promedio del depto.)",
                                 "casos": "Casos acumulados"}, texto="departamento")
        fig.update_layout(title="Clima promedio vs. casos totales por departamento")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Spearman entre departamentos: {corr_geo[variable]:.2f}"
                   if not np.isnan(corr_geo[variable]) else "Correlación no calculable.")


def pestana_conclusiones(m, col):
    """Conclusiones generadas a partir de los datos filtrados + tabla de métricas."""
    st.subheader("Qué dicen los datos")
    ranking = est.ranking_departamentos(m, col)
    top3 = ranking.head(3)
    estac = est.estacionalidad(m, col)
    mes_pico = MESES[int(estac.loc[estac["indice"].idxmax(), "mes"]) - 1]
    mes_valle = MESES[int(estac.loc[estac["indice"].idxmin(), "mes"]) - 1]
    anual = m.groupby("anio")[col].sum()
    rez = calcular_rezagos(m, col).dropna(subset=["spearman"])
    _, corr_geo = est.relacion_geografica(m, col)

    st.markdown(f"- **Geográfico:** {', '.join(top3.index)} concentran "
                f"{top3['participacion_pct'].sum():.0f} % de los casos de la selección.")
    st.markdown(f"- **Temporal:** el año con más casos fue **{anual.idxmax()}** "
                f"({anual.max():,.0f}); el mes más activo en promedio es **{mes_pico}** "
                f"y el más bajo **{mes_valle}**.")
    if not rez.empty:
        mejor = rez.loc[rez["spearman"].abs().idxmax()]
        st.markdown(f"- **Ambiental (en el tiempo):** la asociación más marcada es con "
                    f"*{mejor['variable']}* a **{int(mejor['rezago_meses'])} mes(es)** de rezago "
                    f"(Spearman {mejor['spearman']:.2f}, {est.describir_correlacion(mejor['spearman'])}).")
    st.markdown(f"- **Ambiental (entre departamentos):** temperatura media vs. casos: "
                f"{est.describir_correlacion(corr_geo['temp_media'])}; lluvia vs. casos: "
                f"{est.describir_correlacion(corr_geo['lluvia_mm'])}.")

    st.subheader("Métricas estadísticas (NumPy / Pandas)")
    izq, der = st.columns([2, 3])
    izq.dataframe(est.tabla_metricas(m, col), hide_index=True, use_container_width=True)
    der.dataframe(ranking.round(1).head(10), use_container_width=True)

    st.subheader("Limitaciones")
    st.markdown(
        "- Correlación no implica causalidad: la altitud, la urbanización, el acceso a agua y la "
        "notificación también influyen.\n"
        "- El clima corresponde a la **capital** del departamento, que no representa todo su territorio.\n"
        "- SIVIGILA mide casos **notificados**; hay subregistro y cambios en la vigilancia entre años.\n")


#---
#Pagina principal
#---
def main():
    """Construye la barra lateral de filtros y las cuatro pestañas."""
    st.title("🦟 De los datos a la historia: dengue en Colombia, 2020-2025")
    datos = cargar_datos()
    if datos is None:
        st.error("Faltan archivos en data/processed. Ejecuta primero `python limpieza.py`.")
        st.stop()
    mensual = datos["mensual"]

    st.sidebar.header("Filtros")
    nombres = sorted(mensual["departamento"].unique())
    deptos = st.sidebar.multiselect("Departamentos", nombres, default=nombres)
    anios = st.sidebar.slider("Rango de años", ANIO_INICIO, ANIO_FIN, (ANIO_INICIO, ANIO_FIN))
    tipo = st.sidebar.selectbox("Tipo de caso", list(COLUMNA_TIPO))
    tiene_poblacion = mensual["poblacion"].notna().any()
    opciones = ["Casos", "Incidencia por 100.000 hab."] if tiene_poblacion else ["Casos"]
    metrica = st.sidebar.radio("Métrica del mapa y ranking", opciones)
    t_min, t_max = math.floor(mensual["temp_media"].min()), math.ceil(mensual["temp_media"].max())
    rango_temp = st.sidebar.slider("Temperatura media mensual (°C)", t_min, t_max, (t_min, t_max),
                                   help="Aplica a la pestaña de correlación ambiental.")

    col = COLUMNA_TIPO[tipo]
    m = filtrar(mensual, deptos, anios)
    if m.empty:
        st.warning("Selecciona al menos un departamento.")
        st.stop()

    t1, t2, t3, t4 = st.tabs(["1. Pregunta", "2. Análisis espaciotemporal",
                              "3. Correlación ambiental", "4. Conclusiones"])
    with t1:
        pestana_intro(m, col)
    with t2:
        pestana_espaciotemporal(m, datos, deptos, anios, col, metrica.startswith("Incidencia"))
    with t3:
        pestana_ambiental(m, col, rango_temp)
    with t4:
        pestana_conclusiones(m, col)


main()
