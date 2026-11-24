# 🦟 De los Datos a la Historia: dengue en Colombia (2020-2025)

Dashboard interactivo en Streamlit que responde: **¿qué factores geográficos, temporales y
ambientales están relacionados con la incidencia del dengue en Colombia?**

## Estructura
```
├── app.py                 # Dashboard (Streamlit)
├── config.py              # Rutas, catálogo de departamentos, alias de columnas
├── descargar_clima.py     # Descarga clima diario de NASA POWER
├── limpieza.py            # Carga, limpieza, unión y exportación
├── estadisticas.py        # Métricas y correlaciones (NumPy/Pandas)
├── requirements.txt
└── data/
    ├── raw/               # SIVIGILA 2020-2025 + clima
    └── processed/         # CSV listos para el dashboard 
```

## Cómo reproducirlo
1. `pip install -r requirements.txt`
2. Copia los archivos anuales de SIVIGILA (dengue 210 del 2020-2025) en `data/raw/`.
3. `python descargar_clima.py` → crea `data/raw/clima_diario_2020_2025.csv`.
4. `python limpieza.py` → genera `data/processed/*.csv` y `auditoria_limpieza.csv`.
5. `streamlit run app.py`

Si `limpieza.py` dice que faltan columnas, revisa los nombres reales de tus archivos y agrega
el alias en `ALIAS_COLUMNAS` de `config.py`. Verifica también en `config.py` los códigos de
`AJUSTES_DESCARTADOS` y `CONDICION_MUERTO` contra el diccionario de datos del INS.

## Despliegue en Streamlit Cloud
1. Sube el repositorio a GitHub **incluyendo `data/processed/`** (pesa pocos MB).
2. Entra a https://share.streamlit.io → *New app* → elige el repo, rama `main` y archivo `app.py`.
3. *Deploy*. Streamlit instala `requirements.txt` automáticamente.

## Decisiones metodológicas
- Duplicados exactos eliminados sobre las columnas completas del archivo original.
- Se excluyen casos descartados (campo AJUSTE) y el evento de mortalidad (para no duplicar).
- Departamentos y municipios unificados por código DIVIPOLA, no por nombre.
- Clima: NASA POWER en la capital de cada departamento (limitación documentada).
- Correlaciones con rezago estandarizadas dentro de cada departamento.

## Fuentes
SIVIGILA – Instituto Nacional de Salud · NASA POWER · DANE (población).
