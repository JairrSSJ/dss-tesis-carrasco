# -*- coding: utf-8 -*-
"""
Interfaz del DSS — Framework VSM Digital + Madurez Digital + Priorización Lean 4.0
Caso: Industrias Marcelo S.A.C. (metalmecánica MTO)
"""

from __future__ import annotations

import copy
import hashlib
import html
import inspect
import io
import json
import os
import platform
import re
import sys
import time
import traceback
import unicodedata
from dataclasses import asdict, is_dataclass
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

# #############################################################################
# PARTE 1 — CONFIGURACIÓN, PLACEHOLDER DEL DSS Y UTILIDADES
# #############################################################################

st.set_page_config(page_title="DSS Lead Time — Industrias Marcelo", layout="wide",
                   initial_sidebar_state="expanded")

PENDIENTE = "PENDIENTE_DATOS"

PETROLEO, SALVIA, VIOLETA, NARANJA = "#1B4F63", "#8DAA91", "#8C86A0", "#D9822B"

TITULO = "DSS de Lead Time — Industrias Marcelo S.A.C."
SUBTITULO = ("Framework basado en VSM Digital y evaluación de madurez digital "
             "para optimizar el Lead Time en una industria metalmecánica MTO")

ejecutar_dss = None
ERROR_IMPORTACION_DSS = None
try:
    from dss_core import ejecutar_dss
except Exception:
    ERROR_IMPORTACION_DSS = traceback.format_exc()

DSS_DISPONIBLE = callable(ejecutar_dss)

LINEA_BASE = {
    "Lead Time promedio": {"valor": 24.5, "unidad": "días", "menor_es_mejor": True},
    "WIP": {"valor": 18, "unidad": "unidades", "menor_es_mejor": True},
    "PCE": {"valor": 8.5, "unidad": "%", "menor_es_mejor": False},
    "Pedidos fuera de fecha": {"valor": 42, "unidad": "%", "menor_es_mejor": True},
}

KPI_RUTAS: dict[str, dict] = {
    "Lead Time promedio": {"df": "resumen_ejecutivo.diagnostico_C1", "indicador": "Lead Time promedio",
                           "columna_valor": "valor"},
    "WIP": {"df": "resumen_ejecutivo.diagnostico_C1", "indicador": "WIP Plegado-Soldadura",
            "columna_valor": "valor"},
    "PCE": {"df": "resumen_ejecutivo.diagnostico_C1", "indicador": "PCE",
            "columna_valor": "valor"},
    "Pedidos fuera de fecha": {"df": "resumen_ejecutivo.diagnostico_C1", "indicador": "Pedidos fuera de fecha",
                               "columna_valor": "valor"},
}

MAPA_SALIDA = {
    "c1": {"ruta": "resumen_ejecutivo.diagnostico_C1", "claves": ["c1", "vsm", "diagnostico"]},
    "c2": {"ruta": "resumen_ejecutivo.madurez_C2", "claves": ["c2", "madurez"]},
    "c3": {"ruta": "resumen_ejecutivo.priorizacion_C3", "claves": ["c3", "priorizacion"]},
    "escenarios": {"ruta": "resumen_ejecutivo.escenarios", "claves": ["escenarios", "escenario"]},
    "des": {"ruta": "control_flujo", "claves": ["control_flujo"]},
    "cp11": {"ruta": "resumen_ejecutivo.comparacion_resultados", "claves": ["comparacion_resultados"]},
    "comparacion": {"ruta": "resumen_ejecutivo.comparacion_resultados", "claves": ["comparacion_resultados"]},
    "restricciones": {"ruta": "resumen_ejecutivo.restricciones", "claves": ["restricciones"]},
    "decision": {"ruta": "resumen_ejecutivo.decision", "claves": ["decision"]},
}

TITULOS_BLOQUE = {
    "c1": "Diagnóstico C1 — VSM Digital",
    "c2": "Madurez digital C2",
    "c3": "Priorización C3 — Lean 4.0",
    "escenarios": "Escenarios TO-BE",
    "des": "Simulación de eventos discretos (DES)",
    "cp11": "Evaluación CP11",
    "comparacion": "Comparación Lead Time / WIP / PCE",
    "restricciones": "Restricciones",
    "decision": "Decisión final",
}

BLOQUES_RESUMEN = ["c1", "c2", "c3", "escenarios", "comparacion", "restricciones", "decision"]

ETAPAS = [
    ("1. Dato de entrada", []),
    ("2. Diagnóstico", ["c1", "c2"]),
    ("3. Intervención", ["c3"]),
    ("4. Escenario", ["escenarios", "des"]),
    ("5. Resultado", ["cp11", "comparacion", "restricciones", "decision"]),
]

ESTRUCTURA_DATOS_ENTRADA = {
    "CP1": {"tablas": ["df_ordenes", "df_procesos", "df_recursos", "df_madurez", "df_simulacion"], "dicts": []},
    "CP2": {"tablas": ["df_rutas_orden", "df_vsm", "df_indicadores_vsm"], "dicts": []},
    "CP3": {"tablas": ["df_carga_capacidad"], "dicts": []},
    "CP4": {"tablas": ["df_madurez_respuestas"], "dicts": []},
    "CP5": {"tablas": ["df_mapeo_brechas_intervenciones", "df_alternativas_cp5"], "dicts": []},
    "CP6": {"tablas": ["df_priorizacion", "df_matriz_F", "df_contribucion_L"], "dicts": []},
    "CP7": {"tablas": ["df_operaciones", "df_recursos", "df_rutas"], "dicts": ["param_llegadas"]},
    "CP8": {"tablas": ["df_trazabilidad_calibracion"], "dicts": ["criterios_aceptacion"]},
    "CP9": {"tablas": ["df_modificaciones_tobe"], "dicts": ["catalogo_escenarios"]},
    "CP10": {"tablas": ["df_replicas", "df_resumen_escenarios"], "dicts": ["parametros_simulacion"]},
    "CP11": {"tablas": ["df_evaluacion_cp11"], "dicts": ["METAS_TOBE"]},
}

PARAMETROS_REQUERIDOS = [f"{cp}.{nombre}" for cp, e in ESTRUCTURA_DATOS_ENTRADA.items()
                         for nombre in e["tablas"] + e["dicts"]]

COLUMNAS_ESPERADAS = {
    "CP1.df_ordenes": ["id_orden", "fecha_ingreso", "fecha_comprometida", "producto_ruta",
                       "cantidad_unidades", "estado", "observaciones", "estado_dato"],
    "CP1.df_procesos": ["operacion", "orden_proceso", "ruta_variable", "tiempo_ciclo_min",
                        "tiempo_setup_min", "tiempo_espera_min", "tiempo_traslado_min", "wip_unidades",
                        "tiempo_disponible_turno_min", "estado_dato"],
    "CP2.df_indicadores_vsm": ["indicador", "valor", "unidad", "estado_dato"],
    "CP4.df_madurez_respuestas": ["dimension", "subdimension", "indicador", "pregunta",
                                  "puntuacion_1_5", "observaciones", "estado_dato"],
}

COLUMNAS_OPCIONALES = {"observaciones"}

HOJAS_ALIAS = {
    "CP5_df_mapeo_brechas": ("CP5", "df_mapeo_brechas_intervenciones"),
}

COLUMNAS_TRAZABILIDAD_DSS = [
    "id_dato", "id_diagnostico", "id_brecha", "id_intervencion", "id_escenario",
    "LT_asis", "WIP_asis", "PCE_asis", "LT_tobe", "WIP_tobe", "PCE_tobe",
    "delta_LT_pct", "delta_WIP_pct", "delta_PCE_pct", "estado_final", "fecha_estado",
]

MODULOS = [
    "Inicio (carga de datos)",
    "C1 VSM Digital",
    "C2 Madurez Digital",
    "C3 Priorización Lean 4.0",
    "Escenarios TO-BE",
    "DES (simulación)",
    "Evaluación CP11",
    "Trazabilidad DSS",
    "Reporte final",
]

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Poppins:wght@500;600;700&display=swap');
html, body, [class*="st-"], .stMarkdown, p, label, li {{ font-family: 'Inter', sans-serif; }}
h1, h2, h3, h4 {{ font-family: 'Poppins', sans-serif !important; color: {PETROLEO}; letter-spacing: -0.01em; }}
h1 {{ font-weight: 700; font-size: 1.85rem !important; margin-bottom: 0.2rem; }}
.subtitulo {{ color: {VIOLETA}; font-size: 0.97rem; margin-bottom: 1.1rem; }}
div[data-testid="stMetric"] {{ background: #F2F5F4; border-left: 5px solid {SALVIA};
    padding: 0.7rem 0.9rem; border-radius: 4px; }}
div[data-testid="stMetricLabel"] p {{ color: {PETROLEO}; font-weight: 500; }}
button[kind="primary"] {{ background-color: {PETROLEO}; border-color: {PETROLEO}; }}
section[data-testid="stSidebar"] {{ background: #F2F5F4; }}
.caja-pendiente {{ border-left: 5px solid {NARANJA}; background: #FBF1E6;
    padding: 0.7rem 1rem; border-radius: 4px; margin: 0.4rem 0 0.8rem 0; }}
.caja-ok {{ border-left: 5px solid {SALVIA}; background: #EEF4EF;
    padding: 0.7rem 1rem; border-radius: 4px; margin: 0.4rem 0 0.8rem 0; }}
</style>
""",
    unsafe_allow_html=True,
)


def normalizar(texto) -> str:
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", "_", t.strip().lower())


def etiqueta(clave) -> str:
    t = str(clave).replace("_", " ").strip()
    return t[:1].upper() + t[1:]


def es_escalar(v) -> bool:
    return v is None or isinstance(v, (str, int, float, bool, np.number, np.bool_))


def es_figura(o):
    modulo = type(o).__module__ or ""
    if modulo.startswith("matplotlib.figure"):
        return "matplotlib"
    if modulo.startswith("plotly.graph_objs") and type(o).__name__ == "Figure":
        return "plotly"
    return None


def formatear(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, (bool, np.bool_)):
        return "Sí" if v else "No"
    if isinstance(v, (float, np.floating)):
        if np.isnan(v):
            return "—"
        return f"{v:.4f}".rstrip("0").rstrip(".")
    return str(v)


def a_serializable(o):
    if o is None or isinstance(o, (str, bool)):
        return o
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if (np.isnan(f) or np.isinf(f)) else f
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return a_serializable(o.tolist())
    if isinstance(o, pd.DataFrame):
        return {"__tipo__": "DataFrame", "columnas": [str(c) for c in o.columns],
                "filas": a_serializable(o.to_dict(orient="records"))}
    if isinstance(o, pd.Series):
        return a_serializable(o.to_dict())
    if isinstance(o, dict):
        return {str(k): a_serializable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [a_serializable(v) for v in o]
    if isinstance(o, (datetime, pd.Timestamp)):
        return o.isoformat()
    if is_dataclass(o) and not isinstance(o, type):
        return a_serializable(asdict(o))
    if es_figura(o):
        return f"<figura {type(o).__name__}>"
    return str(o)


def hash_json(obj) -> str:
    cadena = json.dumps(a_serializable(obj), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest()


_FALTA = object()


def get_path(d, ruta: str):
    actual = d
    for parte in ruta.split("."):
        if isinstance(actual, dict) and parte in actual:
            actual = actual[parte]
        else:
            return _FALTA
    return actual


def set_path(d: dict, ruta: str, valor) -> None:
    partes = ruta.split(".")
    for p in partes[:-1]:
        d = d.setdefault(p, {})
    d[partes[-1]] = valor


def aplanar(obj, ruta="") -> list[tuple[str, object]]:
    obj = a_serializable(obj)
    salida = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            salida += aplanar(v, f"{ruta}.{k}" if ruta else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            salida += aplanar(v, f"{ruta}[{i}]")
    else:
        salida.append((ruta, obj))
    return salida


def buscar_pendientes(obj) -> list[str]:
    return [r for r, v in aplanar(obj) if isinstance(v, str) and PENDIENTE in v]


def coincide(clave, fragmentos: list[str]) -> bool:
    kn = normalizar(clave)
    palabras = set(kn.split("_"))
    for f in fragmentos:
        if (len(f) < 5 and f in palabras) or (len(f) >= 5 and f in kn):
            return True
    return False


def buscar_numero(obj, fragmentos: list[str]):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if (isinstance(v, (int, float, np.number)) and not isinstance(v, (bool, np.bool_))
                    and all(f in normalizar(k) for f in fragmentos)):
                return str(k), float(v)
        for k, v in obj.items():
            if isinstance(v, dict):
                hallado = buscar_numero(v, fragmentos)
                if hallado:
                    return f"{k}.{hallado[0]}", hallado[1]
    return None


def tabla(df: pd.DataFrame) -> None:
    try:
        st.dataframe(df)
    except Exception:
        st.dataframe(df.astype(str))


def aviso_pendiente(texto_usuario: str, detalle_tecnico: str | None = None) -> None:
    st.markdown(f"<div class='caja-pendiente'><b>{PENDIENTE}</b><br>{texto_usuario}</div>",
                unsafe_allow_html=True)
    if detalle_tecnico:
        st.caption(detalle_tecnico)


def mostrar(obj, prof: int = 0) -> None:
    if obj is None:
        st.caption("—")
        return
    fig = es_figura(obj)
    if fig == "matplotlib":
        st.pyplot(obj)
        return
    if fig == "plotly":
        st.plotly_chart(obj)
        return
    if isinstance(obj, str):
        (st.warning if PENDIENTE in obj else st.write)(obj)
        return
    if isinstance(obj, (bool, int, float, np.number, np.bool_)):
        st.write(formatear(obj))
        return
    if isinstance(obj, pd.DataFrame):
        tabla(obj)
        return
    if isinstance(obj, pd.Series):
        tabla(obj.to_frame("valor"))
        return
    if isinstance(obj, np.ndarray):
        if obj.ndim == 1:
            tabla(pd.DataFrame({"valor": obj}))
        elif obj.ndim == 2:
            tabla(pd.DataFrame(obj))
        else:
            st.write(f"Arreglo de forma {obj.shape}")
        return
    if isinstance(obj, dict):
        escalares = {k: v for k, v in obj.items() if es_escalar(v)}
        if escalares:
            tabla(pd.DataFrame({"Concepto": [etiqueta(k) for k in escalares],
                                "Valor": [formatear(v) for v in escalares.values()]}))
        for k, v in obj.items():
            if es_escalar(v):
                continue
            if prof == 0:
                with st.expander(etiqueta(k), expanded=False):
                    mostrar(v, prof + 1)
            else:
                st.markdown(f"{'#' * min(prof + 3, 6)} {etiqueta(k)}")
                mostrar(v, prof + 1)
        return
    if isinstance(obj, (list, tuple)):
        if obj and all(isinstance(x, dict) and all(es_escalar(y) for y in x.values()) for x in obj):
            tabla(pd.DataFrame(a_serializable(list(obj))))
        elif all(es_escalar(x) for x in obj):
            tabla(pd.DataFrame({"valor": [formatear(x) for x in obj]}))
        else:
            for i, item in enumerate(obj, 1):
                st.markdown(f"**Elemento {i}**")
                mostrar(item, prof + 1)
        return
    st.write(str(obj))


def extraer_tablas(obj, ruta="salida") -> list[tuple[str, pd.DataFrame]]:
    salida = []
    if isinstance(obj, pd.DataFrame):
        salida.append((ruta, obj))
    elif isinstance(obj, np.ndarray) and obj.ndim in (1, 2):
        salida.append((ruta, pd.DataFrame(obj)))
    elif isinstance(obj, dict):
        esc = {k: v for k, v in obj.items() if es_escalar(v)}
        if esc:
            salida.append((ruta, pd.DataFrame({"concepto": list(esc),
                                               "valor": [formatear(v) for v in esc.values()]})))
        for k, v in obj.items():
            if not es_escalar(v):
                salida += extraer_tablas(v, f"{ruta}.{k}")
    elif isinstance(obj, (list, tuple)):
        if obj and all(isinstance(x, dict) for x in obj):
            salida.append((ruta, pd.DataFrame(a_serializable(list(obj)))))
        elif obj and all(es_escalar(x) for x in obj):
            salida.append((ruta, pd.DataFrame({"valor": [formatear(x) for x in obj]})))
        else:
            for i, x in enumerate(obj):
                salida += extraer_tablas(x, f"{ruta}[{i}]")
    return salida


# #############################################################################
# PARTE 2 — DATOS, EJECUCIÓN, BLOQUES, COMPARACIÓN Y EXPORTACIÓN
# #############################################################################


@st.cache_data(show_spinner=False)
def leer_bytes(nombre: str, contenido: bytes) -> dict[str, pd.DataFrame]:
    n = nombre.lower()
    if n.endswith(".csv"):
        df = None
        for enc in ("utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(io.BytesIO(contenido), sep=None, engine="python", encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if df is None:
            raise ValueError("No se pudo leer la codificación del CSV.")
        hojas = {os.path.splitext(nombre)[0]: df}
    elif n.endswith((".xlsx", ".xlsm")):
        hojas = pd.read_excel(io.BytesIO(contenido), sheet_name=None)
    else:
        raise ValueError("Formato no admitido. Use .xlsx o .csv.")
    limpias = {}
    for h, d in hojas.items():
        d = d.dropna(how="all")
        sobrantes = [c for c in d.columns if str(c).startswith("Unnamed") and d[c].isna().all()]
        limpias[str(h)] = d.drop(columns=sobrantes).reset_index(drop=True)
    return limpias


def _parsear_celda(v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, str):
        if not v.strip() or v.strip().lower() == "none":
            return None
        try:
            return json.loads(v)
        except ValueError:
            return v.strip()
    return v


def _valor_vacio(v) -> bool:
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return True
    return isinstance(v, str) and (not v.strip() or v.strip().lower() == "none" or PENDIENTE in v)


def _es_hoja_parametros(df: pd.DataFrame) -> bool:
    return {"clave", "valor"}.issubset({normalizar(c) for c in df.columns})


def clasificar_hoja(nombre: str):
    nombre = str(nombre).strip()
    if nombre in HOJAS_ALIAS:
        return HOJAS_ALIAS[nombre]
    m = re.match(r"^(CP\d+)_(.+)$", nombre, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1).upper(), m.group(2).strip()


def construir_datos_entrada(hojas: dict[str, pd.DataFrame]) -> dict:
    datos: dict = {}
    for nombre, df in hojas.items():
        if _es_hoja_parametros(df):
            d = df.copy()
            d.columns = [normalizar(c) for c in d.columns]
            if "grupo" not in d.columns:
                continue
            for _, fila in d.iterrows():
                if pd.isna(fila["clave"]) or pd.isna(fila["grupo"]):
                    continue
                clave, grupo = str(fila["clave"]).strip(), str(fila["grupo"]).strip()
                if not clave or not re.match(r"^CP\d+\.[^.\s]+$", grupo, flags=re.IGNORECASE):
                    continue
                cp, nombre_dict = grupo.split(".", 1)
                set_path(datos, f"{cp.upper()}.{nombre_dict}.{clave}", _parsear_celda(fila["valor"]))
        else:
            clas = clasificar_hoja(nombre)
            if clas is None:
                continue
            cp, nombre_df = clas
            datos.setdefault(cp, {})[nombre_df] = df.copy()
    return datos


def validar_entrada(hojas: dict[str, pd.DataFrame], datos: dict) -> list[dict]:
    pend: list[dict] = []

    def add(origen: str, detalle: str) -> None:
        pend.append({"Origen": origen, "Detalle": detalle})

    for hoja, df in hojas.items():
        if _es_hoja_parametros(df):
            d = df.copy()
            d.columns = [normalizar(c) for c in d.columns]
            if "grupo" not in d.columns:
                add(hoja, "La hoja de parámetros no tiene la columna «grupo»; se ignora.")
                continue
            for _, f in d.iterrows():
                if pd.isna(f["clave"]):
                    continue
                clave = str(f["clave"]).strip()
                grupo = "" if pd.isna(f["grupo"]) else str(f["grupo"]).strip()
                if not re.match(r"^CP\d+\.[^.\s]+$", grupo, flags=re.IGNORECASE):
                    add(hoja, f"Parámetro «{clave}»: grupo «{grupo}» inválido; se ignora.")
                elif _valor_vacio(f["valor"]):
                    add(hoja, f"{grupo}.{clave}: sin valor.")
            continue
        if clasificar_hoja(hoja) is None:
            add(hoja, "El nombre de la hoja no sigue la convención CPn_nombre_de_tabla; se ignora.")
            continue
        if df.empty:
            add(hoja, "La tabla no tiene filas.")
            continue
        for i, col in enumerate(df.columns):
            serie = df.iloc[:, i]
            marcadas = int(serie.astype(str).str.contains(PENDIENTE, regex=False).sum())
            if marcadas:
                add(hoja, f"Columna «{col}»: {marcadas} celda(s) marcadas como {PENDIENTE}.")
            if normalizar(col) in COLUMNAS_OPCIONALES:
                continue
            vacias = int(serie.isna().sum())
            if vacias:
                add(hoja, f"Columna «{col}»: {vacias} celda(s) vacía(s).")

    for ruta in PARAMETROS_REQUERIDOS:
        if get_path(datos, ruta) is _FALTA:
            add("Estructura esperada", f"Falta «{ruta}».")
    for ruta, columnas in COLUMNAS_ESPERADAS.items():
        tabla_ = get_path(datos, ruta)
        if isinstance(tabla_, pd.DataFrame):
            faltan = [c for c in columnas if c not in [str(x) for x in tabla_.columns]]
            if faltan:
                add(ruta, "Faltan las columnas: " + ", ".join(faltan) + ".")
    return pend


for _k, _v in {"hojas": {}, "datos_entrada": {}, "pendientes": [], "archivos": [],
               "historial": [], "ultima": None}.items():
    st.session_state.setdefault(_k, _v)


def modulo_dss():
    return sys.modules.get(getattr(ejecutar_dss, "__module__", ""), None) if DSS_DISPONIBLE else None


def huella_codigo() -> str:
    try:
        with open(inspect.getsourcefile(modulo_dss()), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return PENDIENTE


def version_dss() -> str:
    m = modulo_dss()
    return str(getattr(m, "__version__", PENDIENTE)) if m else PENDIENTE


def ejecutar_registrado(pendientes: list[dict]) -> dict:
    datos = st.session_state["datos_entrada"]
    registro = {
        "id": len(st.session_state["historial"]) + 1,
        "marca_tiempo": datetime.now().astimezone().isoformat(timespec="seconds"),
        "archivos": copy.deepcopy(st.session_state["archivos"]),
        "hojas": {h: {"filas": int(d.shape[0]), "columnas": [str(c) for c in d.columns]}
                  for h, d in st.session_state["hojas"].items()},
        "hash_entrada": hash_json(datos),
        "entrada": copy.deepcopy(datos),
        "pendientes_entrada": pendientes,
        "version_dss": version_dss(),
        "huella_codigo_dss": huella_codigo(),
        "salida": None,
        "error": None,
        "duracion_s": None,
    }
    inicio = time.perf_counter()
    try:
        registro["salida"] = ejecutar_dss(copy.deepcopy(datos))
    except Exception:
        registro["error"] = traceback.format_exc()
    registro["duracion_s"] = round(time.perf_counter() - inicio, 2)
    st.session_state["historial"].append(registro)
    st.session_state["ultima"] = registro["id"]
    return registro


def registro_activo():
    uid = st.session_state.get("ultima")
    if uid is None:
        return None
    return st.session_state["historial"][uid - 1]


def buscar_bloque(salida, bloque_id: str) -> list[tuple[str, object]]:
    cfg = MAPA_SALIDA[bloque_id]
    if cfg["ruta"]:
        v = get_path(salida, cfg["ruta"])
        return [] if v is _FALTA else [(cfg["ruta"], v)]
    if not isinstance(salida, dict):
        return []
    primer_nivel = [(str(k), v) for k, v in salida.items() if coincide(k, cfg["claves"])]
    if primer_nivel:
        return primer_nivel

    def dfs(d: dict, prefijo: str, nivel: int):
        out = []
        for k, v in d.items():
            ruta = f"{prefijo}.{k}" if prefijo else str(k)
            if coincide(k, cfg["claves"]):
                out.append((ruta, v))
            elif isinstance(v, dict) and nivel < 3:
                out += dfs(v, ruta, nivel + 1)
        return out

    return dfs(salida, "", 0)


def estado_bloque(hallados) -> str:
    if not hallados:
        return PENDIENTE
    if all(v is None for _, v in hallados):
        return PENDIENTE
    if any(buscar_pendientes(v) for _, v in hallados):
        return f"Parcial (contiene {PENDIENTE})"
    return "Disponible"


def render_bloque(bloque_id: str, salida, prof: int = 0) -> None:
    titulo = TITULOS_BLOQUE[bloque_id]
    hallados = buscar_bloque(salida, bloque_id)
    if estado_bloque(hallados) == PENDIENTE:
        aviso_pendiente(
            f"La salida del DSS no incluye resultados identificables para «{titulo}». "
            "No se muestra ningún valor de reemplazo.",
            f"Para el equipo técnico: devuélvalo desde ejecutar_dss o indique su ruta en "
            f"MAPA_SALIDA['{bloque_id}']['ruta'] (inicio de app.py).")
        return
    for ruta, valor in hallados:
        st.caption(f"Origen en la salida del DSS: `{ruta}`")
        pend = buscar_pendientes(valor)
        if pend:
            aviso_pendiente(f"Este bloque contiene {len(pend)} elemento(s) marcados como {PENDIENTE}.")
            tabla(pd.DataFrame({"ruta": pend}))
        mostrar(valor, prof)


def pagina_con_ejecucion(titulo: str, ayuda: str):
    st.markdown(f"## {titulo}")
    st.write(ayuda)
    reg = registro_activo()
    if reg is None:
        st.info("Todavía no hay resultados. Cargue los datos y ejecute el DSS en «Inicio (carga de datos)».")
        return None
    if reg["error"]:
        st.error("La última ejecución terminó con error y no hay resultados que mostrar. "
                 "Revise el detalle en «Inicio (carga de datos)».")
        return None
    st.caption(f"Ejecución #{reg['id']} · {reg['marca_tiempo']} · huella de entrada {reg['hash_entrada'][:12]}")
    return reg


def valor_desde_df(salida, instr: dict):
    ruta_df = instr["df"]
    df = get_path(salida, ruta_df)
    if df is _FALTA or df is None:
        return None, ruta_df, f"El DSS no devolvió «{ruta_df}»."
    if not isinstance(df, pd.DataFrame):
        return None, ruta_df, f"«{ruta_df}» no es un DataFrame."
    col_ind = instr.get("columna_indicador", "indicador")
    col_val = instr.get("columna_valor", "valor")
    col_est = instr.get("columna_estado", "estado_dato")
    if col_ind not in df.columns or col_val not in df.columns:
        return None, ruta_df, f"Faltan las columnas «{col_ind}» o «{col_val}» en «{ruta_df}»."
    objetivo = normalizar(instr["indicador"])
    filas = df[df[col_ind].astype(str).map(normalizar) == objetivo]
    if filas.empty:
        return None, ruta_df, f"No hay una fila con el indicador «{instr['indicador']}»."
    if len(filas) > 1:
        return None, ruta_df, f"Hay {len(filas)} filas con el indicador «{instr['indicador']}»; no se elige ninguna."
    fila = filas.iloc[0]
    origen = f"{ruta_df} [{col_ind} = {instr['indicador']}] → {col_val}"
    if col_est in df.columns and PENDIENTE in str(fila[col_est]):
        return None, origen, f"El DSS marcó este dato como {fila[col_est]}."
    valor = pd.to_numeric(fila[col_val], errors="coerce")
    if pd.isna(valor):
        return None, origen, "El valor está vacío o no es numérico."
    return float(valor), origen, None


def calcular_comparacion(salida) -> list[dict]:
    filas = []
    for nombre, ref in LINEA_BASE.items():
        valor = ruta = motivo = None
        instr = KPI_RUTAS.get(nombre)
        if instr is None:
            motivo = "No se configuró su ubicación en KPI_RUTAS."
        elif not isinstance(salida, dict):
            motivo = "La salida del DSS no es un diccionario."
        elif isinstance(instr, dict):
            valor, ruta, motivo = valor_desde_df(salida, instr)
        else:
            h = get_path(salida, str(instr))
            if h is not _FALTA and isinstance(h, (int, float, np.number)) and not isinstance(h, bool):
                valor, ruta = float(h), str(instr)
            else:
                ruta, motivo = str(instr), f"No se encontró un número en «{instr}»."
        fila = {"nombre": nombre, "unidad": ref["unidad"], "base": ref["valor"], "valor": valor,
                "ruta": ruta, "motivo": motivo, "menor_es_mejor": ref["menor_es_mejor"]}
        if valor is not None:
            fila["delta"] = valor - ref["valor"]
            fila["delta_pct"] = (valor - ref["valor"]) / ref["valor"] * 100 if ref["valor"] else None
            fila["lectura"] = "Coincide" if abs(fila["delta"]) < 0.005 else "Difiere"
        filas.append(fila)
    return filas


def df_comparacion(filas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Indicador": f["nombre"],
        "Unidad": f["unidad"],
        "Línea base declarada": f"{f['base']:g}",
        "Valor medido por el DSS (AS-IS)": f"{f['valor']:g}" if f["valor"] is not None else PENDIENTE,
        "Diferencia": f"{f['delta']:+.2f}" if f["valor"] is not None else PENDIENTE,
        "Diferencia %": f"{f['delta_pct']:+.1f} %" if f.get("delta_pct") is not None else PENDIENTE,
        "Lectura": f.get("lectura", PENDIENTE),
        "Origen del valor": f["ruta"] if f["valor"] is not None else (f["motivo"] or "—"),
    } for f in filas])


def render_comparacion(salida) -> None:
    st.markdown("#### Comparación AS-IS vs TO-BE entregada por el DSS")
    render_bloque("comparacion", salida)

    st.markdown("#### Verificación del AS-IS medido frente a la línea base declarada")
    filas = calcular_comparacion(salida)
    cols = st.columns(len(filas))
    for col, f in zip(cols, filas):
        with col:
            if f["valor"] is None:
                st.metric(f["nombre"], PENDIENTE)
                st.caption(f"Línea base: {f['base']:g} {f['unidad']}")
            else:
                st.metric(f["nombre"], f"{f['valor']:g} {f['unidad']}",
                          delta=f"{f['delta']:+.2f} vs. línea base ({f['base']:g})", delta_color="off")
    tabla(df_comparacion(filas))
    con_valor = {f["nombre"]: f["delta_pct"] for f in filas if f.get("delta_pct") is not None}
    if con_valor:
        st.markdown("**Diferencia porcentual entre el valor medido por el DSS y la línea base**")
        st.bar_chart(pd.DataFrame({"Diferencia %": con_valor}), color=PETROLEO)
    faltan = [f for f in filas if f["valor"] is None]
    if faltan:
        aviso_pendiente("El DSS no entregó valores utilizables para: "
                        + ", ".join(f["nombre"] for f in faltan) + ". No se estiman.")
        tabla(pd.DataFrame({"Indicador": [f["nombre"] for f in faltan],
                            "Motivo": [f["motivo"] for f in faltan]}))
    st.caption("Estos valores son del diagnóstico (AS-IS) y se comparan con la línea base declarada del caso.")


def leer_decision_global(salida):
    if not isinstance(salida, dict) or "decision_global" not in salida:
        return None, True
    v = salida["decision_global"]
    if v is None:
        return None, True
    texto = str(v).strip()
    if not texto:
        return None, True
    return texto, PENDIENTE in texto


def render_decision_final(salida) -> None:
    st.markdown("#### Decisión global del DSS")
    texto, pendiente = leer_decision_global(salida)
    if pendiente:
        if texto:
            aviso_pendiente(html.escape(texto).replace("\n", "<br>"))
        else:
            aviso_pendiente("El DSS no entregó una decisión global («decision_global»). "
                            "No se formula ninguna recomendación desde la interfaz.")
    else:
        st.success(texto)
    st.markdown("#### Detalle de la decisión (`resumen_ejecutivo.decision`)")
    render_bloque("decision", salida)


def render_trazabilidad_dss(reg: dict) -> None:
    salida = reg["salida"]
    df = salida.get("df_trazabilidad_dss", _FALTA) if isinstance(salida, dict) else _FALTA
    if df is _FALTA or df is None:
        aviso_pendiente("El DSS no devolvió «df_trazabilidad_dss». No se genera ni se estima ninguna tabla.")
        return
    if not isinstance(df, pd.DataFrame):
        aviso_pendiente("«df_trazabilidad_dss» no es un DataFrame; no se puede mostrar como tabla.")
        return
    if df.empty:
        st.info("La tabla «df_trazabilidad_dss» no tiene filas.")
        return
    faltan = [c for c in COLUMNAS_TRAZABILIDAD_DSS if c not in [str(x) for x in df.columns]]
    if faltan:
        st.warning("A la tabla le faltan las columnas esperadas: " + ", ".join(faltan) + ".")
    tabla(df)
    st.caption(f"{df.shape[0]} fila(s) × {df.shape[1]} columna(s).")
    try:
        st.download_button("Descargar tabla de trazabilidad del DSS (.csv)",
                           df.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"df_trazabilidad_dss_ejecucion_{reg['id']}.csv",
                           mime="text/csv", key=f"dl_traz_dss_{reg['id']}")
    except Exception as e:
        st.warning(f"No se pudo generar el CSV de trazabilidad: {e}")


def cadena_trazabilidad(reg: dict) -> pd.DataFrame:
    filas = []
    for etapa, bloques in ETAPAS:
        if not bloques:
            n_pend = len(reg["pendientes_entrada"])
            archivos = ", ".join(a["nombre"] for a in reg["archivos"]) or "—"
            filas.append({"Etapa": etapa,
                          "Elementos": f"Archivos: {archivos} · huella {reg['hash_entrada'][:12]}",
                          "Estado": "Completo" if n_pend == 0 else f"{n_pend} {PENDIENTE}"})
            continue
        partes, estados = [], []
        for b in bloques:
            hall = buscar_bloque(reg["salida"], b)
            est = estado_bloque(hall)
            estados.append(est)
            ruta = ", ".join(r for r, _ in hall) if hall else "—"
            partes.append(f"{TITULOS_BLOQUE[b]} → {ruta}")
        filas.append({"Etapa": etapa, "Elementos": " | ".join(partes),
                      "Estado": " / ".join(estados)})
    return pd.DataFrame(filas)


def paquete_trazabilidad(reg: dict) -> dict:
    return {
        "ejecucion": {"id": reg["id"], "marca_tiempo": reg["marca_tiempo"], "duracion_s": reg["duracion_s"]},
        "dss": {"version": reg["version_dss"], "huella_codigo": reg["huella_codigo_dss"]},
        "entorno": {"python": platform.python_version(), "streamlit": st.__version__,
                    "pandas": pd.__version__, "numpy": np.__version__},
        "archivos_cargados": reg["archivos"],
        "hojas": reg["hojas"],
        "cadena_trazabilidad": cadena_trazabilidad(reg).to_dict("records"),
        "entrada": {"hash_sha256": reg["hash_entrada"], "datos": a_serializable(reg["entrada"]),
                    "pendientes": reg["pendientes_entrada"]},
        "salida": a_serializable(reg["salida"]),
        "pendientes_en_salida": buscar_pendientes(reg["salida"]),
        "error": reg["error"],
    }


def _nombre_hoja(base: str, usados: set) -> str:
    limpio = re.sub(r"[\[\]\*\?/\\:]", "_", str(base))[:28] or "hoja"
    nombre, n = limpio, 1
    while nombre in usados:
        n += 1
        nombre = f"{limpio[:25]}_{n}"
    usados.add(nombre)
    return nombre


def filas_resumen(reg: dict) -> list[dict]:
    filas = []
    for b in BLOQUES_RESUMEN:
        hall = buscar_bloque(reg["salida"], b)
        filas.append({"Bloque": TITULOS_BLOQUE[b], "Estado": estado_bloque(hall),
                      "Ruta en la salida del DSS": ", ".join(r for r, _ in hall) if hall else PENDIENTE})
    return filas


def excel_reporte(reg: dict) -> bytes:
    memoria = io.BytesIO()
    usados: set[str] = set()
    salida = reg["salida"]
    with pd.ExcelWriter(memoria, engine="openpyxl") as xw:
        meta = {"ejecucion": reg["id"], "fecha": reg["marca_tiempo"], "duracion_s": reg["duracion_s"],
                "hash_entrada": reg["hash_entrada"], "version_dss": reg["version_dss"],
                "huella_codigo_dss": reg["huella_codigo_dss"], "python": platform.python_version(),
                "streamlit": st.__version__}
        pd.DataFrame({"campo": list(meta), "valor": [str(v) for v in meta.values()]}).to_excel(
            xw, sheet_name=_nombre_hoja("Metadatos", usados), index=False)
        pd.DataFrame(filas_resumen(reg)).to_excel(xw, sheet_name=_nombre_hoja("Resumen", usados), index=False)
        df_comparacion(calcular_comparacion(salida)).to_excel(
            xw, sheet_name=_nombre_hoja("Comparacion", usados), index=False)
        cadena_trazabilidad(reg).to_excel(xw, sheet_name=_nombre_hoja("Trazabilidad", usados), index=False)
        df_traz = salida.get("df_trazabilidad_dss") if isinstance(salida, dict) else None
        if isinstance(df_traz, pd.DataFrame):
            df_traz.to_excel(xw, sheet_name=_nombre_hoja("Trazabilidad_DSS", usados), index=False)
        if reg["pendientes_entrada"]:
            pd.DataFrame(reg["pendientes_entrada"]).to_excel(
                xw, sheet_name=_nombre_hoja("Pendientes_entrada", usados), index=False)
        for b in list(TITULOS_BLOQUE):
            for ruta, v in buscar_bloque(salida, b):
                for r2, df in extraer_tablas(v, f"{b}_{ruta}"):
                    df.to_excel(xw, sheet_name=_nombre_hoja(r2, usados), index=False)
    return memoria.getvalue()


def csv_reporte(reg: dict) -> bytes:
    filas = []
    for b in list(TITULOS_BLOQUE):
        hall = buscar_bloque(reg["salida"], b)
        if not hall:
            filas.append({"bloque": TITULOS_BLOQUE[b], "ruta": "", "concepto": "", "valor": PENDIENTE})
            continue
        for ruta, v in hall:
            for r2, val in aplanar(v, ruta):
                filas.append({"bloque": TITULOS_BLOQUE[b], "ruta": ruta, "concepto": r2,
                              "valor": formatear(val)})
    return pd.DataFrame(filas).to_csv(index=False).encode("utf-8-sig")


# #############################################################################
# PARTE 3 — PÁGINAS Y NAVEGACIÓN
# #############################################################################


def pagina_inicio() -> None:
    st.markdown("## Inicio — carga de datos y ejecución")
    st.write("Siga los tres pasos: **1)** cargue los datos de planta, **2)** revise que no falten datos, "
             "**3)** ejecute el DSS. Luego navegue por los módulos del menú lateral.")

    with st.expander("¿Qué formato debe tener el archivo?"):
        st.markdown(
            "- **Excel (.xlsx)** con una hoja por tabla, o **CSV (.csv)** con el mismo nombre de la hoja.\n"
            "- El nombre de cada hoja es `CPn_nombre_de_la_tabla`; por ejemplo `CP1_df_ordenes` se carga "
            "como la tabla `df_ordenes` del CP1.\n"
            "- Los parámetros (diccionarios de CP7 a CP11) van en una hoja con las columnas `clave`, `valor` "
            "y `grupo`; el grupo indica el destino, por ejemplo `CP7.param_llegadas`.\n"
            f"- Las celdas vacías o marcadas como `{PENDIENTE}` se reportan y no se completan.\n"
            "- La lista completa de hojas está en el README.")

    st.markdown("### Paso 1. Cargar datos")
    archivos = st.file_uploader("Archivos de datos (.xlsx o .csv)", type=["xlsx", "xlsm", "csv"],
                                accept_multiple_files=True, key="archivos_subidos")
    if archivos:
        hojas_total: dict[str, pd.DataFrame] = {}
        meta = []
        for a in archivos:
            contenido = a.getvalue()
            try:
                hojas = leer_bytes(a.name, contenido)
            except Exception as e:
                st.error(f"No se pudo leer «{a.name}»: {e}")
                continue
            meta.append({"nombre": a.name, "bytes": len(contenido),
                         "sha256": hashlib.sha256(contenido).hexdigest()})
            stem = os.path.splitext(a.name)[0]
            for h, df in hojas.items():
                hojas_total[h if h not in hojas_total else f"{stem}_{h}"] = df
        if hojas_total:
            datos = construir_datos_entrada(hojas_total)
            st.session_state.update(hojas=hojas_total, datos_entrada=datos, archivos=meta,
                                    pendientes=validar_entrada(hojas_total, datos))
    elif st.session_state["hojas"]:
        st.info("Se conservan los datos cargados antes en esta sesión. Para reemplazarlos, suba nuevos archivos.")

    hojas = st.session_state["hojas"]
    if hojas:
        if st.button("Quitar los datos cargados"):
            st.session_state.update(hojas={}, datos_entrada={}, pendientes=[], archivos=[])
            st.rerun()

    st.markdown("### Paso 2. Revisar los datos")
    if not hojas:
        st.info("Aún no se han cargado datos.")
    else:
        for h, df in hojas.items():
            tipo = "parámetros" if _es_hoja_parametros(df) else "tabla"
            with st.expander(f"{h} — {tipo}, {df.shape[0]} fila(s) × {df.shape[1]} columna(s)"):
                tabla(df.head(200))
                if df.shape[0] > 200:
                    st.caption("Se muestran las primeras 200 filas.")
        pend = st.session_state["pendientes"]
        if pend:
            aviso_pendiente(f"Se detectaron {len(pend)} dato(s) faltante(s). La interfaz no los completa; "
                            "deben medirse o confirmarse en planta.")
            tabla(pd.DataFrame(pend))
        else:
            st.markdown("<div class='caja-ok'>No se detectaron datos vacíos ni marcados como "
                        f"{PENDIENTE}.</div>", unsafe_allow_html=True)
        if not PARAMETROS_REQUERIDOS:
            st.caption(f"{PENDIENTE}: aún no se definió la lista de parámetros obligatorios "
                       "(PARAMETROS_REQUERIDOS en app.py). La revisión solo detecta celdas vacías o marcadas.")

    st.markdown("### Paso 3. Ejecutar el DSS")
    if not DSS_DISPONIBLE:
        aviso_pendiente("El motor del DSS no está conectado, por lo que no se puede ejecutar.",
                        "Para el equipo técnico: cree dss_core.py con ejecutar_dss(datos_entrada) o pegue la "
                        "función en la OPCIÓN B de app.py.")
        if ERROR_IMPORTACION_DSS:
            with st.expander("Detalle técnico de la importación"):
                st.code(ERROR_IMPORTACION_DSS, language="text")
    elif not hojas:
        st.info("Cargue los datos para habilitar la ejecución.")
    else:
        pend = st.session_state["pendientes"]
        permitir = True
        if pend:
            permitir = st.checkbox(f"Ejecutar de todas formas con {PENDIENTE}. Las celdas vacías llegarán "
                                   "vacías al DSS, que deberá reportarlas.")
        if st.button("Ejecutar DSS", type="primary", disabled=bool(pend) and not permitir):
            with st.spinner("Ejecutando el DSS. La simulación puede tardar varios minutos…"):
                reg = ejecutar_registrado(pend)
            if reg["error"]:
                st.error("El DSS no pudo completar la ejecución. Revise que los datos estén completos y en "
                         "las unidades correctas.")
                with st.expander("Detalle técnico (para el equipo de la tesis)"):
                    st.code(reg["error"], language="text")
            else:
                st.success(f"Ejecución #{reg['id']} completada en {reg['duracion_s']} s. "
                           "Abra los módulos desde el menú lateral o vaya a «Reporte final».")
        reg = registro_activo()
        if reg and reg["error"]:
            st.warning(f"La ejecución #{reg['id']} terminó con error.")


def pagina_modulo(bloque_id: str, ayuda: str) -> None:
    reg = pagina_con_ejecucion(TITULOS_BLOQUE[bloque_id], ayuda)
    if reg is not None:
        render_bloque(bloque_id, reg["salida"])


def pagina_trazabilidad() -> None:
    st.markdown("## Trazabilidad DSS")
    st.write("Cadena completa: dato → diagnóstico → intervención → escenario → resultado.")
    hist = st.session_state["historial"]
    if not hist:
        st.info("La trazabilidad se genera al ejecutar el DSS.")
        return
    ids = [r["id"] for r in hist][::-1]
    elegido = st.selectbox("Ejecución a documentar", ids,
                           format_func=lambda i: f"#{i} — {hist[i-1]['marca_tiempo']}"
                           + (" (con error)" if hist[i-1]["error"] else ""))
    reg = hist[elegido - 1]
    st.caption(f"Huella SHA-256 de la entrada: {reg['hash_entrada']}")
    st.caption(f"Versión del DSS: {reg['version_dss']} · huella del código: {reg['huella_codigo_dss']} · "
               f"duración: {reg['duracion_s']} s")
    if reg["archivos"]:
        st.markdown("**Archivos de entrada**")
        tabla(pd.DataFrame(reg["archivos"]))
    if reg["error"]:
        st.error("Esta ejecución terminó con error; no hay salida que trazar.")
        with st.expander("Detalle técnico"):
            st.code(reg["error"], language="text")
    else:
        st.markdown("**Cadena de trazabilidad**")
        tabla(cadena_trazabilidad(reg))
        st.caption("La ubicación de cada bloque en la salida se define en MAPA_SALIDA (app.py).")
        st.markdown("**Trazabilidad dato → resultado entregada por el DSS (`df_trazabilidad_dss`)**")
        render_trazabilidad_dss(reg)
    if reg["pendientes_entrada"]:
        st.markdown(f"**{PENDIENTE} en la entrada**")
        tabla(pd.DataFrame(reg["pendientes_entrada"]))
    st.download_button("Descargar paquete de trazabilidad (.json)",
                       json.dumps(paquete_trazabilidad(reg), ensure_ascii=False, indent=2),
                       file_name=f"trazabilidad_dss_ejecucion_{reg['id']}.json", mime="application/json")
    if len(hist) > 1:
        st.markdown("**Ejecuciones de la sesión**")
        tabla(pd.DataFrame([{
            "Ejecución": r["id"], "Fecha": r["marca_tiempo"], "Huella de entrada": r["hash_entrada"][:12],
            "Pendientes en la entrada": len(r["pendientes_entrada"]), "Duración (s)": r["duracion_s"],
            "Estado": "Error" if r["error"] else "Completada"} for r in hist]))


def pagina_reporte() -> None:
    reg = pagina_con_ejecucion(
        "Reporte final — resumen ejecutivo",
        "Siete bloques con lo que entregó el DSS. Lo que no se entregó figura como "
        f"{PENDIENTE}; no se estima ni se completa.")
    if reg is None:
        return
    salida = reg["salida"]

    st.markdown("### Estado de los bloques")
    tabla(pd.DataFrame(filas_resumen(reg)))

    for i, b in enumerate(BLOQUES_RESUMEN, 1):
        st.markdown(f"### {i}. {TITULOS_BLOQUE[b]}")
        if b == "comparacion":
            render_comparacion(salida)
        elif b == "decision":
            render_decision_final(salida)
        else:
            render_bloque(b, salida)

    st.markdown("### Exportar el reporte")
    c1, c2 = st.columns(2)
    try:
        c1.download_button("Descargar reporte en Excel (.xlsx)", excel_reporte(reg),
                           file_name=f"reporte_dss_ejecucion_{reg['id']}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        c1.warning(f"No se pudo generar el Excel: {e}")
    try:
        c2.download_button("Descargar reporte en CSV (.csv)", csv_reporte(reg),
                           file_name=f"reporte_dss_ejecucion_{reg['id']}.csv", mime="text/csv")
    except Exception as e:
        c2.warning(f"No se pudo generar el CSV: {e}")
    st.caption("El Excel incluye resumen, comparación, trazabilidad, pendientes y las tablas de cada bloque. "
               "El CSV contiene todos los valores de la salida en formato plano.")


with st.sidebar:
    st.markdown("### Módulos")
    modulo = st.radio("Seleccione un módulo", MODULOS, key="modulo", label_visibility="collapsed")
    st.divider()
    st.markdown("**Estado**")
    st.caption(("Motor DSS conectado" if DSS_DISPONIBLE else f"Motor DSS: {PENDIENTE}"))
    st.caption(f"Hojas/tablas cargadas: {len(st.session_state['hojas'])}")
    st.caption(f"Datos pendientes en la entrada: {len(st.session_state['pendientes'])}")
    _r = registro_activo()
    st.caption("Última ejecución: " + (f"#{_r['id']} ({'con error' if _r['error'] else 'completada'})"
                                       if _r else "ninguna"))
    if DSS_DISPONIBLE:
        try:
            st.caption(f"Firma: `ejecutar_dss{inspect.signature(ejecutar_dss)}`")
        except (TypeError, ValueError):
            pass
    st.divider()
    if st.button("Reiniciar la sesión"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

st.title(TITULO)
st.markdown(f"<div class='subtitulo'>{SUBTITULO}</div>", unsafe_allow_html=True)

AYUDAS = {
    "c1": "Mapa de la cadena de valor con datos de planta: dónde se pierde tiempo entre la recepción "
          "del pedido y la entrega.",
    "c2": "Nivel de preparación tecnológica de la planta para incorporar herramientas digitales.",
    "c3": "Herramientas Lean 4.0 ordenadas según el diagnóstico y la madurez de la planta.",
    "escenarios": "Escenarios de mejora (TO-BE) construidos a partir de la priorización.",
    "des": "Estado de ejecución de cada módulo del DSS (control de flujo), con su mensaje.",
    "cp11": "Evaluación de los resultados de la simulación (checkpoint 11 del artefacto).",
}

if modulo == MODULOS[0]:
    pagina_inicio()
elif modulo == MODULOS[1]:
    pagina_modulo("c1", AYUDAS["c1"])
elif modulo == MODULOS[2]:
    pagina_modulo("c2", AYUDAS["c2"])
elif modulo == MODULOS[3]:
    pagina_modulo("c3", AYUDAS["c3"])
elif modulo == MODULOS[4]:
    pagina_modulo("escenarios", AYUDAS["escenarios"])
elif modulo == MODULOS[5]:
    pagina_modulo("des", AYUDAS["des"])
elif modulo == MODULOS[6]:
    pagina_modulo("cp11", AYUDAS["cp11"])
elif modulo == MODULOS[7]:
    pagina_trazabilidad()
else:
    pagina_reporte()
