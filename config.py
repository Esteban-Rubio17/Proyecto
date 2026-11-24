"""Configuración compartida del proyecto: rutas, constantes y catálogos."""
from pathlib import Path

RUTA_RAW = Path("data/raw")
RUTA_PROCESADOS = Path("data/processed")
ARCHIVO_CLIMA = RUTA_RAW / "clima_diario_2020_2025.csv"

ANIO_INICIO = 2020
ANIO_FIN = 2025

# Código DIVIPOLA del departamento -> (nombre, latitud, longitud de la capital).
# Las coordenadas se usan para (a) descargar el clima y (b) ubicar el mapa.
DEPARTAMENTOS = {
    "05": ("Antioquia", 6.2442, -75.5812),
    "08": ("Atlántico", 10.9639, -74.7964),
    "11": ("Bogotá D.C.", 4.7110, -74.0721),
    "13": ("Bolívar", 10.3910, -75.4794),
    "15": ("Boyacá", 5.5353, -73.3678),
    "17": ("Caldas", 5.0703, -75.5138),
    "18": ("Caquetá", 1.6144, -75.6062),
    "19": ("Cauca", 2.4419, -76.6063),
    "20": ("Cesar", 10.4631, -73.2532),
    "23": ("Córdoba", 8.7479, -75.8814),
    "25": ("Cundinamarca", 4.3010, -74.8036),  # Girardot: zona cálida del dpto.
    "27": ("Chocó", 5.6947, -76.6583),
    "41": ("Huila", 2.9273, -75.2819),
    "44": ("La Guajira", 11.5444, -72.9072),
    "47": ("Magdalena", 11.2408, -74.1990),
    "50": ("Meta", 4.1420, -73.6266),
    "52": ("Nariño", 1.2136, -77.2811),
    "54": ("Norte de Santander", 7.8939, -72.5078),
    "63": ("Quindío", 4.5339, -75.6811),
    "66": ("Risaralda", 4.8133, -75.6961),
    "68": ("Santander", 7.1193, -73.1227),
    "70": ("Sucre", 9.3047, -75.3978),
    "73": ("Tolima", 4.4389, -75.2322),
    "76": ("Valle del Cauca", 3.4516, -76.5320),
    "81": ("Arauca", 7.0847, -70.7591),
    "85": ("Casanare", 5.3378, -72.3959),
    "86": ("Putumayo", 1.1478, -76.6469),
    "88": ("San Andrés", 12.5847, -81.7006),
    "91": ("Amazonas", -4.2153, -69.9406),
    "94": ("Guainía", 3.8653, -67.9239),
    "95": ("Guaviare", 2.5729, -72.6459),
    "97": ("Vaupés", 1.2530, -70.2340),
    "99": ("Vichada", 6.1890, -67.4859),
}


EVENTOS = {210: "Dengue", 220: "Dengue grave"}


AJUSTES_DESCARTADOS = {"6", "D"}


CONDICION_MUERTO = 2

# Unidad de medida de la edad (UNI_MED) -> factor para convertir a años.
FACTOR_EDAD_A_ANIOS = {1: 1.0, 2: 1 / 12, 3: 1 / 365, 4: 1 / 8760, 5: 1 / 525600}

CODIGO_COLOMBIA = 170

# Nombre canónico -> posibles nombres de columna en los archivos (ya normalizados:
# minúsculas, sin tildes, sin guion bajo final). Si tus archivos usan otros nombres,
# agrégalos aquí.
ALIAS_COLUMNAS = {
    "fecha": ["fec_not", "fecha_notificacion", "fecha_de_notificacion"],
    "anio": ["ano", "anio", "year"],
    "semana": ["semana", "semana_epidemiologica", "sem"],
    "cod_dpto": ["cod_dpto_o", "cod_dpto_proce", "codigo_departamento", "cod_dpto"],
    "cod_mun": ["cod_mun_o", "cod_mun_proce", "codigo_municipio", "cod_mun"],
    "departamento": ["departamento_ocurrencia", "ndep_proce", "nombre_departamento", "departamento"],
    "municipio": ["municipio_ocurrencia", "nmun_proce", "nombre_municipio", "municipio"],
    "edad": ["edad"],
    "unidad_edad": ["uni_med", "unidad_medida"],
    "sexo": ["sexo"],
    "area": ["area"],
    "condicion_final": ["con_fin", "condicion_final"],
    "ajuste": ["ajuste"],
    "pais": ["cod_pais_o", "cod_pais"],
    "cod_evento": ["cod_eve", "cod_evento"],
    "nom_evento": ["nom_eve", "nombre_evento", "evento"],
}
COLUMNAS_OBLIGATORIAS = ["fecha", "cod_dpto"]
