# -*- coding: utf-8 -*-
"""
dss_core.py — Motor del DSS (CP1 a CP12)
Tesis: Framework basado en VSM Digital y evaluación de madurez digital para
optimizar el Lead Time en una industria metalmecánica MTO.
Caso: Industrias Marcelo S.A.C.

Función maestra: ejecutar_dss(datos_entrada)  → la llama app.py (Streamlit).

Consolidación del notebook de Colab (tesis_carrasco.py):
- Sin celdas de Colab (se eliminó `!pip install simpy`; no hay drive.mount ni files.upload).
- Sin print() de verificación intermedia: los bloques "VERIFICACIÓN DE ESTRUCTURA" y
  "ANÁLISIS PRELIMINAR" se omitieron (siguen en el notebook original).
- Imports unificados al inicio; las constantes ESTADO_* idénticas se definen una sola vez.
- Colisiones de nombres resueltas:
    * df_recursos (CP7)            → df_recursos_cp7   (df_recursos de CP1 se conserva)
    * ESTADO_PENDIENTE (CP12)      → ESTADO_PENDIENTE_DSS = "PENDIENTE_DATOS"
      (ESTADO_PENDIENTE = "PENDIENTE_CONFIRMAR" se conserva para CP1–CP10)
- P9 (generador de datos sintéticos de prueba) NO forma parte de CP1–CP12 y no se incluye.

Cambios de la versión 1.1.0 respecto de la 1.0.0:
    * COLUMNAS_MTO_REQUERIDAS usa los nombres de CP1 (fecha_ingreso, fecha_comprometida,
      cantidad_unidades).
    * ejecutar_dss_control y ejecutar_dss acceden a datos_entrada con .get(...): una tabla
      o un CP ausente se reporta como PENDIENTE_DATOS en vez de lanzar KeyError.
    * generar_resumen_ejecutivo acepta catalogo_escenarios como DataFrame o dict
      (dict → DataFrame con columnas id_intervencion y escenario).
    * construir_trazabilidad_dss usa df_priorizacion y df_modificaciones_tobe para completar
      id_intervencion (ID real) e id_brecha; id_dato e id_diagnostico siguen en None.
- matplotlib se importa solo dentro de visualizar_vsm_basico (no es requerida por ejecutar_dss).
"""

import numpy as np
import pandas as pd
import simpy  # CP7: reservado para el modelo DES (en el notebook solo se importaba)
from datetime import datetime


# ============================================================
# CP1 — ESTRUCTURA DE DATOS DE ENTRADA
# Framework: VSM Digital + Madurez Digital + Lean 4.0 + DES
# ============================================================

# ------------------------------------------------------------
# 1. CATÁLOGO DE ESTADOS DE LOS DATOS
# ------------------------------------------------------------

ESTADO_CONFIRMADO = "CONFIRMADO"
ESTADO_PENDIENTE = "PENDIENTE_CONFIRMAR"
ESTADO_VALIDAR = "VALIDAR_EMPRESA"


# ------------------------------------------------------------
# 2. ÓRDENES MTO
# ------------------------------------------------------------

df_ordenes = pd.DataFrame(columns=[
    "id_orden",
    "fecha_ingreso",
    "fecha_comprometida",
    "producto_ruta",
    "cantidad_unidades",
    "estado",
    "observaciones",
    "estado_dato"
])

# Ejemplo de estructura inicial.
# Los valores reales se cargarán posteriormente.
df_ordenes.loc[0] = [
    "ORD_001",
    None,
    None,
    None,
    None,
    None,
    None,
    ESTADO_PENDIENTE
]


# ------------------------------------------------------------
# 3. PROCESOS / OPERACIONES
# ------------------------------------------------------------

operaciones = [
    "Recepción MTO",
    "Diseño/ingeniería de detalle",
    "Corte (láser/punzonado)",
    "Plegado",
    "Soldadura",
    "Armado",
    "Acabado superficial",
    "Pintura",
    "Inspección final",
    "Despacho"
]

df_procesos = pd.DataFrame({
    "operacion": operaciones,
    "orden_proceso": range(1, len(operaciones) + 1),
    "ruta_variable": [False, False, True, True, True,
                      True, True, True, True, False],
    "tiempo_ciclo_min": [None, None, 45, None, 180,
                         180, None, None, None, None],
    "tiempo_setup_min": [None] * len(operaciones),
    "tiempo_espera_min": [None] * len(operaciones),
    "tiempo_traslado_min": [None] * len(operaciones),
    "wip_unidades": [None] * len(operaciones),
    "tiempo_disponible_turno_min": [None] * len(operaciones),
    "estado_dato": [ESTADO_PENDIENTE] * len(operaciones)
})

# Datos actualmente confirmados
df_procesos.loc[
    df_procesos["operacion"] == "Corte (láser/punzonado)",
    "estado_dato"
] = ESTADO_CONFIRMADO

df_procesos.loc[
    df_procesos["operacion"] == "Soldadura",
    "estado_dato"
] = ESTADO_CONFIRMADO

df_procesos.loc[
    df_procesos["operacion"] == "Armado",
    "estado_dato"
] = ESTADO_CONFIRMADO


# WIP confirmado entre Plegado y Soldadura.
# Se registra como referencia del sistema actual.
wip_plegado_soldadura = 18


# ------------------------------------------------------------
# 4. RECURSOS Y CAPACIDADES
# ------------------------------------------------------------

df_recursos = pd.DataFrame(columns=[
    "operacion",
    "tipo_recurso",
    "cantidad_recursos",
    "capacidad_unidad_hora",
    "disponibilidad_porcentaje",
    "horas_turno",
    "observaciones",
    "estado_dato"
])

# Se dejan las filas preparadas para completar posteriormente.
for operacion in operaciones:
    df_recursos.loc[len(df_recursos)] = [
        operacion,
        None,
        None,
        None,
        None,
        None,
        None,
        ESTADO_PENDIENTE
    ]


# ------------------------------------------------------------
# 5. MADUREZ DIGITAL
# ------------------------------------------------------------

dimensiones_madurez = [
    "Procesos",
    "Personas",
    "Tecnología",
    "Organización"
]

df_madurez = pd.DataFrame(columns=[
    "dimension",
    "indicador",
    "pregunta",
    "puntuacion_1_5",
    "observaciones",
    "estado_dato"
])

# Se crean únicamente las dimensiones.
# Los indicadores y preguntas se definirán posteriormente.
for dimension in dimensiones_madurez:
    df_madurez.loc[len(df_madurez)] = [
        dimension,
        None,
        None,
        None,
        None,
        ESTADO_PENDIENTE
    ]


# ------------------------------------------------------------
# 6. PARÁMETROS PARA SIMULACIÓN DES
# ------------------------------------------------------------

df_simulacion = pd.DataFrame(columns=[
    "operacion",
    "ruta",
    "regla_liberacion",
    "tiempo_proceso_min",
    "tiempo_espera_min",
    "recursos_disponibles",
    "capacidad",
    "tiempo_disponible_turno_min",
    "distribucion_tiempo_proceso",
    "parametros_distribucion",
    "observaciones",
    "estado_dato"
])

for operacion in operaciones:
    df_simulacion.loc[len(df_simulacion)] = [
        operacion,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        ESTADO_PENDIENTE
    ]


# ------------------------------------------------------------
# 7. INDICADORES ACTUALES DEL SISTEMA
# ------------------------------------------------------------

df_indicadores = pd.DataFrame({
    "indicador": [
        "Lead Time promedio",
        "WIP promedio entre Plegado y Soldadura",
        "PCE",
        "Pedidos fuera de fecha"
    ],
    "valor": [
        24.5,
        18,
        8.5,
        42
    ],
    "unidad": [
        "días hábiles",
        "unidades",
        "%",
        "%"
    ],
    "periodo_referencia": [
        "Situación actual",
        "Situación actual",
        "Situación actual",
        "Último semestre"
    ],
    "estado_dato": [
        ESTADO_CONFIRMADO,
        ESTADO_CONFIRMADO,
        ESTADO_CONFIRMADO,
        ESTADO_CONFIRMADO
    ]
})


# [Omitido] CP1: verificación de estructura (prints) — ver tesis_carrasco.py, líneas 246-271.

# ============================================================
# CP2 — C1: VSM DIGITAL
# ============================================================




# ============================================================
# 1. RUTAS ESPECÍFICAS POR ORDEN MTO
# ============================================================

df_rutas_orden = pd.DataFrame(columns=[
    "id_orden",
    "secuencia",
    "operacion",
    "aplica",
    "estado_dato"
])


# ============================================================
# 2. DETALLE VSM POR ORDEN Y OPERACIÓN
# ============================================================

df_vsm = pd.DataFrame(columns=[
    "id_orden",
    "producto_ruta",
    "secuencia",
    "operacion",
    "tiempo_ciclo_min",
    "tiempo_espera_min",
    "tiempo_traslado_min",
    "wip_unidades",
    "tiempo_valor_agregado_min",
    "tiempo_disponible_turno_min",
    "recursos",
    "aplica",
    "estado_dato"
])


# ============================================================
# 3. FUNCIÓN PARA AGREGAR UNA OPERACIÓN AL VSM
# ============================================================

def agregar_operacion_vsm(
    id_orden,
    producto_ruta,
    secuencia,
    operacion,
    tiempo_ciclo_min=None,
    tiempo_espera_min=None,
    tiempo_traslado_min=None,
    wip_unidades=None,
    tiempo_valor_agregado_min=None,
    tiempo_disponible_turno_min=None,
    recursos=None,
    aplica=True,
    estado_dato=ESTADO_PENDIENTE
):

    global df_vsm

    nueva_fila = {
        "id_orden": id_orden,
        "producto_ruta": producto_ruta,
        "secuencia": secuencia,
        "operacion": operacion,
        "tiempo_ciclo_min": tiempo_ciclo_min,
        "tiempo_espera_min": tiempo_espera_min,
        "tiempo_traslado_min": tiempo_traslado_min,
        "wip_unidades": wip_unidades,
        "tiempo_valor_agregado_min": tiempo_valor_agregado_min,
        "tiempo_disponible_turno_min": tiempo_disponible_turno_min,
        "recursos": recursos,
        "aplica": aplica,
        "estado_dato": estado_dato
    }

    df_vsm = pd.concat(
        [df_vsm, pd.DataFrame([nueva_fila])],
        ignore_index=True
    )


# ============================================================
# DATOS CONFIRMADOS ACTUALES
# ============================================================

datos_confirmados = {
    "Corte (láser/punzonado)": 45,
    "Soldadura": 180,
    "Armado": 180
}

for operacion, tiempo in datos_confirmados.items():

    df_procesos.loc[
        df_procesos["operacion"] == operacion,
        "tiempo_ciclo_min"
    ] = tiempo

    df_procesos.loc[
        df_procesos["operacion"] == operacion,
        "estado_dato"
    ] = ESTADO_CONFIRMADO


# WIP confirmado entre Plegado y Soldadura
WIP_PLEGADO_SOLDADURA = 18

# Indicadores globales confirmados
LT_GLOBAL_CONFIRMADO = 24.5
PCE_GLOBAL_CONFIRMADO = 8.5
PEDIDOS_FUERA_FECHA = 42.0


# ============================================================
# 4. MOTOR DE CÁLCULO DEL LEAD TIME
# ============================================================

def calcular_lead_time_orden(df, id_orden):
    """
    Calcula LT de una orden solamente cuando
    existen los datos necesarios.
    """

    datos = df[
        (df["id_orden"] == id_orden) &
        (df["aplica"] == True)
    ].copy()

    if datos.empty:
        return np.nan

    columnas_necesarias = [
        "tiempo_ciclo_min",
        "tiempo_espera_min",
        "tiempo_traslado_min"
    ]

    # Si falta algún dato necesario, no se inventa.
    if datos[columnas_necesarias].isna().any().any():
        return np.nan

    return datos[columnas_necesarias].sum().sum()


# ============================================================
# 5. CÁLCULO DEL WIP
# ============================================================

def calcular_wip_promedio(df):
    """
    Calcula WIP promedio utilizando únicamente
    los valores disponibles.
    """

    datos = df.dropna(subset=["wip_unidades"])

    if datos.empty:
        return np.nan

    return datos["wip_unidades"].mean()


# ============================================================
# 6. PCE
# ============================================================

def calcular_pce(tiempo_valor_agregado, lead_time):
    """
    PCE expresado en porcentaje.
    """

    if pd.isna(tiempo_valor_agregado) or pd.isna(lead_time):
        return np.nan

    if lead_time <= 0:
        return np.nan

    return (tiempo_valor_agregado / lead_time) * 100


# ============================================================
# 7. INDICADORES GLOBALES DE C1
# ============================================================

def generar_indicadores_vsm(
    lt_confirmado=LT_GLOBAL_CONFIRMADO,
    wip_confirmado=WIP_PLEGADO_SOLDADURA,
    pce_confirmado=PCE_GLOBAL_CONFIRMADO,
    pedidos_fuera_fecha=PEDIDOS_FUERA_FECHA
):

    indicadores = pd.DataFrame({
        "indicador": [
            "Lead Time promedio",
            "WIP Plegado-Soldadura",
            "PCE",
            "Pedidos fuera de fecha"
        ],
        "valor": [
            lt_confirmado,
            wip_confirmado,
            pce_confirmado,
            pedidos_fuera_fecha
        ],
        "unidad": [
            "días hábiles",
            "unidades",
            "%",
            "%"
        ],
        "estado_dato": [
            ESTADO_CONFIRMADO,
            ESTADO_CONFIRMADO,
            ESTADO_CONFIRMADO,
            ESTADO_CONFIRMADO
        ]
    })

    return indicadores


df_indicadores_vsm = generar_indicadores_vsm()
# print(df_indicadores_vsm)  # verificación desactivada


# ============================================================
# 8. IDENTIFICACIÓN DE ACUMULACIONES
# ============================================================

def identificar_acumulaciones(df):

    acumulaciones = df[
        df["wip_unidades"].notna() &
        (df["wip_unidades"] > 0)
    ].copy()

    acumulaciones = acumulaciones.sort_values(
        "wip_unidades",
        ascending=False
    )

    return acumulaciones[
        [
            "id_orden",
            "operacion",
            "wip_unidades",
            "estado_dato"
        ]
    ]


# ============================================================
# 9. IDENTIFICACIÓN DE POSIBLES RESTRICCIONES
# ============================================================

diagnostico_restricciones = pd.DataFrame({
    "zona": [
        "Plegado → Soldadura"
    ],
    "wip_observado": [
        18
    ],
    "clasificacion": [
        "POSIBLE_RESTRICCION"
    ],
    "validacion_requerida": [
        "Análisis carga/capacidad en CP3"
    ]
})

# print("\n=== DIAGNÓSTICO DE RESTRICCIONES ===")  # verificación desactivada
# print(diagnostico_restricciones)  # verificación desactivada


# ============================================================
# 10. RESUMEN AUTOMÁTICO DEL VSM DIGITAL
# ============================================================

def resumen_vsm():

    print("==============================================")
    print("       C1 — VSM DIGITAL | DIAGNÓSTICO AS-IS")
    print("==============================================")

    print(f"\nLead Time promedio : {LT_GLOBAL_CONFIRMADO} días hábiles")
    print(f"WIP Plegado-Soldadura : {WIP_PLEGADO_SOLDADURA} unidades")
    print(f"PCE : {PCE_GLOBAL_CONFIRMADO} %")
    print(f"Pedidos fuera de fecha : {PEDIDOS_FUERA_FECHA} %")

    print("\nDatos de proceso confirmados:")
    print("- Corte/Punzonado : 45 min/lote estándar")
    print("- Soldadura : 180 min/lote estándar")
    print("- Armado : 180 min/lote estándar")

    print("\nAcumulación identificada:")
    print("- Plegado → Soldadura : 18 unidades")

    print("\nEstado del diagnóstico:")
    print("- Posible restricción: Plegado → Soldadura")
    print("- Validación formal: CP3 carga/capacidad")

    print("\nDatos aún pendientes:")
    print("- Tiempos de espera")
    print("- Tiempos de setup")
    print("- Tiempos de traslado")
    print("- Recursos por estación")
    print("- Capacidades")

    print("\n==============================================")


# resumen_vsm()  # llamada de verificación desactivada (la función se conserva)


# ============================================================
# 11. SEGUNDA CAPA: MAPA VSM SIMPLE
# ============================================================

# import matplotlib.pyplot as plt  # movido dentro de visualizar_vsm_basico()

def visualizar_vsm_basico(operaciones):

    import matplotlib.pyplot as plt  # importación diferida: solo si se usa esta función

    fig, ax = plt.subplots(figsize=(16, 4))

    posiciones = range(len(operaciones))

    for i, operacion in enumerate(operaciones):

        ax.text(
            i,
            0.5,
            operacion,
            ha="center",
            va="center",
            bbox=dict(
                boxstyle="round,pad=0.5",
                facecolor="white",
                edgecolor="black"
            )
        )

        if i < len(operaciones) - 1:
            ax.annotate(
                "",
                xy=(i + 0.75, 0.5),
                xytext=(i + 0.25, 0.5),
                arrowprops=dict(arrowstyle="->")
            )

    ax.set_xlim(-0.5, len(operaciones) - 0.5)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("VSM Digital — Flujo base del proceso MTO")

    plt.show()


# visualizar_vsm_basico(operaciones)  # llamada de verificación desactivada (la función se conserva)

# ============================================================
# CP3 — ANÁLISIS CARGA-CAPACIDAD
# ============================================================



operaciones = [
    "Recepción MTO",
    "Diseño/ingeniería de detalle",
    "Corte (láser/punzonado)",
    "Plegado",
    "Soldadura",
    "Armado",
    "Acabado superficial",
    "Pintura",
    "Inspección final",
    "Despacho"
]

df_carga_capacidad = pd.DataFrame({
    "operacion": operaciones,
    "demanda_periodo_unidades": [None] * len(operaciones),
    "tiempo_ciclo_min": [None] * len(operaciones),
    "tiempo_setup_min": [None] * len(operaciones),
    "carga_min_periodo": [None] * len(operaciones),

    "num_operarios": [None] * len(operaciones),
    "num_maquinas": [None] * len(operaciones),

    "horas_turno": [None] * len(operaciones),
    "turnos_periodo": [None] * len(operaciones),
    "dias_trabajados_periodo": [None] * len(operaciones),
    "disponibilidad_pct": [None] * len(operaciones),

    "capacidad_min_periodo": [None] * len(operaciones),

    "rho": [None] * len(operaciones),
    "umbral_saturacion": [None] * len(operaciones),
    "estado": [None] * len(operaciones),
    "evidencia": [None] * len(operaciones),
    "validacion_requerida": [None] * len(operaciones),

    "estado_dato": [ESTADO_PENDIENTE] * len(operaciones)
})


def calcular_carga_estacion(
    demanda_unidades,
    tiempo_ciclo_min,
    tiempo_setup_min=None
):
    """
    Calcula carga en minutos.
    No calcula si faltan datos necesarios.
    """

    if pd.isna(demanda_unidades):
        return np.nan

    if pd.isna(tiempo_ciclo_min):
        return np.nan

    carga = demanda_unidades * tiempo_ciclo_min

    if tiempo_setup_min is not None and not pd.isna(tiempo_setup_min):
        carga += tiempo_setup_min

    return carga


def calcular_capacidad(
    cantidad_recursos,
    horas_turno,
    turnos_periodo,
    dias_trabajados_periodo,
    disponibilidad_pct
):
    """
    Capacidad disponible en minutos durante el periodo.
    """

    valores = [
        cantidad_recursos,
        horas_turno,
        turnos_periodo,
        dias_trabajados_periodo,
        disponibilidad_pct
    ]

    if any(pd.isna(v) for v in valores):
        return np.nan

    capacidad = (
        cantidad_recursos
        * horas_turno
        * turnos_periodo
        * dias_trabajados_periodo
        * 60
        * disponibilidad_pct
    )

    return capacidad


def calcular_rho(carga, capacidad):
    """
    Calcula la relación carga/capacidad.
    """

    if pd.isna(carga) or pd.isna(capacidad):
        return np.nan

    if capacidad <= 0:
        return np.nan

    return carga / capacidad


def clasificar_estacion(
    rho,
    umbral_saturacion=None
):
    """
    Clasifica una estación según rho.
    El umbral de saturación debe validarse metodológicamente.
    """

    if pd.isna(rho):
        return "PENDIENTE_DATOS"

    if rho < 1:
        if (
            umbral_saturacion is not None
            and rho >= umbral_saturacion
        ):
            return "CERCANA_A_SATURACION"

        return "CAPACIDAD_SUFICIENTE"

    if rho > 1:
        return "CARGA_SUPERIOR_A_CAPACIDAD"

    return "SATURACION"


def analizar_carga_capacidad(
    df,
    umbral_saturacion=None
):

    resultados = []

    for _, fila in df.iterrows():

        rho = calcular_rho(
            fila["carga_min_periodo"],
            fila["capacidad_min_periodo"]
        )

        estado = clasificar_estacion(
            rho,
            umbral_saturacion
        )

        if pd.isna(rho):
            evidencia = "Datos de carga/capacidad pendientes"
            validacion = "Completar datos reales con la empresa"
        elif rho > 1:
            evidencia = f"ρ = {rho:.3f}"
            validacion = "Confirmar capacidad y carga real"
        elif (
            umbral_saturacion is not None
            and rho >= umbral_saturacion
        ):
            evidencia = f"ρ = {rho:.3f}"
            validacion = "Validar umbral y condiciones operativas"
        else:
            evidencia = f"ρ = {rho:.3f}"
            validacion = "Validación operativa posterior"

        resultados.append({
            "Estación": fila["operacion"],
            "Carga": fila["carga_min_periodo"],
            "Capacidad": fila["capacidad_min_periodo"],
            "ρ": rho,
            "Estado": estado,
            "Evidencia": evidencia,
            "Validación requerida": validacion
        })

    return pd.DataFrame(resultados)


UMBRAL_SATURACION = None

estaciones_prioritarias = [
    "Plegado",
    "Soldadura",
    "Armado"
]

df_cp3_prioritario = df_carga_capacidad[
    df_carga_capacidad["operacion"].isin(
        estaciones_prioritarias
    )
].copy()

df_cp3_completo = df_carga_capacidad.copy()

resultado_cp3 = analizar_carga_capacidad(
    df_cp3_prioritario,
    umbral_saturacion=UMBRAL_SATURACION
)

# print("=== CP3: ANÁLISIS CARGA-CAPACIDAD (PRELIMINAR) ===")  # verificación desactivada
# print(resultado_cp3)  # verificación desactivada


evidencia_c1 = {
    "zona": "Plegado → Soldadura",
    "wip_observado": 18,
    "clasificacion_c1": "POSIBLE_RESTRICCION",
    "origen": "C1 — VSM Digital",
    "confirmacion_cp3": "PENDIENTE"
}

# Verificación de evidencia heredada de C1 (prints) desactivada.


# ============================================================
# CP4 — C2: MADUREZ DIGITAL
# ============================================================



# ============================================================
# 1. DIMENSIONES Y SUBDIMENSIONES (Cap. III)
# ============================================================

dimensiones_subdimensiones = {
    "Procesos": [
        "Estandarización",
        "Medición",
        "Calidad de datos"
    ],
    "Personas": [
        "Competencias",
        "Participación",
        "Capacidad de adaptación"
    ],
    "Tecnología": [
        "Infraestructura",
        "Conectividad",
        "Captura de datos",
        "Integración de datos"
    ],
    "Organización": [
        "Gobernanza",
        "Recursos",
        "Continuidad de iniciativas"
    ]
}

# ============================================================
# 2. ESCALA PROVISIONAL 1–5
# ============================================================

escala_madurez = {
    1: ("Inicial", "Prácticas incipientes, principalmente informales o inexistentes."),
    2: ("En desarrollo", "Existen algunas prácticas, pero su aplicación aún es parcial o poco consistente."),
    3: ("Definido", "Las prácticas están establecidas y se aplican de manera estructurada."),
    4: ("Gestionado", "Las prácticas son monitoreadas y gestionadas mediante información y seguimiento."),
    5: ("Avanzado", "Las prácticas están consolidadas y presentan un alto nivel de integración y mejora continua.")
}

# ============================================================
# 3. INDICADORES PROPUESTOS (pendientes de validación)
# ============================================================

indicadores_propuestos = {
    "Procesos": [
        ("Estandarización", "Nivel de estandarización de procesos"),
        ("Medición", "Uso de indicadores para medir procesos"),
        ("Calidad de datos", "Disponibilidad y calidad de datos operativos")
    ],
    "Personas": [
        ("Competencias", "Competencias digitales del personal"),
        ("Participación", "Participación del personal en iniciativas de mejora"),
        ("Capacidad de adaptación", "Capacidad de adaptación ante cambios tecnológicos")
    ],
    "Tecnología": [
        ("Infraestructura", "Disponibilidad de infraestructura tecnológica"),
        ("Conectividad", "Nivel de conectividad"),
        ("Captura de datos", "Capacidad de captura de datos"),
        ("Integración de datos", "Nivel de integración de datos")
    ],
    "Organización": [
        ("Gobernanza", "Gobernanza de iniciativas digitales"),
        ("Recursos", "Disponibilidad de recursos"),
        ("Continuidad de iniciativas", "Continuidad de las iniciativas de transformación")
    ]
}

# ============================================================
# 4. DATAFRAME DE RESPUESTAS
# ============================================================

df_madurez_respuestas = pd.DataFrame(columns=[
    "dimension",
    "subdimension",
    "indicador",
    "pregunta",
    "puntuacion_1_5",
    "observaciones",
    "estado_dato"
])

# Cargar estructura inicial con los indicadores propuestos
filas = []
for dimension, indicadores in indicadores_propuestos.items():
    for subdimension, indicador in indicadores:
        filas.append({
            "dimension": dimension,
            "subdimension": subdimension,
            "indicador": indicador,
            "pregunta": None,
            "puntuacion_1_5": None,
            "observaciones": None,
            "estado_dato": ESTADO_PENDIENTE
        })

df_madurez_respuestas = pd.DataFrame(filas)

# ============================================================
# 5. PESOS CONFIGURABLES (inicialmente uniformes)
# ============================================================

pesos_dimensiones = {
    "Procesos": 0.25,
    "Personas": 0.25,
    "Tecnología": 0.25,
    "Organización": 0.25
}

# ============================================================
# 6. CÁLCULO DE MADUREZ POR DIMENSIÓN
# ============================================================

def calcular_madurez_dimension(df, dimension):
    datos = df[
        (df["dimension"] == dimension) &
        (df["puntuacion_1_5"].notna())
    ]

    if datos.empty:
        return None

    return datos["puntuacion_1_5"].mean()

# ============================================================
# 7. CÁLCULO DE MADUREZ GLOBAL
# ============================================================

def calcular_madurez_global(madurez_dimensiones, pesos):
    total_peso = 0
    suma = 0
    for d, valor in madurez_dimensiones.items():
        if valor is not None:
            suma += valor * pesos[d]
            total_peso += pesos[d]
    if total_peso == 0:
        return None
    return suma / total_peso

# ============================================================
# 8. CATEGORÍA GLOBAL CONFIGURABLE (umbrales pendientes)
# ============================================================

umbrales_categoria_global = {
    "Inicial": None,
    "Intermedio": None,
    "Avanzado": None
}

def clasificar_categoria_global(mg, umbrales):
    if mg is None:
        return "PENDIENTE_DATOS"
    if any(v is None for v in umbrales.values()):
        return "PENDIENTE_UMBRALES"
    if mg < umbrales["Intermedio"]:
        return "Inicial"
    elif mg < umbrales["Avanzado"]:
        return "Intermedio"
    else:
        return "Avanzado"

# ============================================================
# 9. HOJA DE RUTA DE BRECHAS
# ============================================================

df_brechas_madurez = pd.DataFrame(columns=[
    "dimension",
    "subdimension",
    "indicador",
    "puntuacion",
    "categoria_brecha",
    "accion_recomendada",
    "brecha_C1",
    "intervencion_Lean4_0",
    "M_i_min",
    "estado_dato"
])

categorias_brecha = [
    "ACCION_INMEDIATA",
    "REQUIERE_ESTANDARIZACION_PREVIA",
    "JUSTIFICA_DIGITALIZACION"
]

# Umbrales de brecha (pendientes de validación)
umbrales_brecha = {
    "ACCION_INMEDIATA": None,
    "REQUIERE_ESTANDARIZACION_PREVIA": None,
    "JUSTIFICA_DIGITALIZACION": None
}

# [Omitido] CP4: sección 10 «Análisis preliminar» (prints y cálculo preliminar) — ver tesis_carrasco.py, líneas 1079-1118.


# ============================================================
# CP5 — MECANISMO C2 → C3
# ============================================================



# ============================================================
# 1. TAXONOMÍA DE BRECHAS DE C1
# ============================================================

TAXONOMIA_BRECHAS_C1 = [
    "espera",
    "acumulacion",
    "capacidad",
    "coordinacion",
    "visibilidad",
    "liberacion"
]

# ============================================================
# 2. CATÁLOGO DE INTERVENCIONES LEAN 4.0
# ============================================================

intervenciones = [
    {"id_intervencion": "I01", "intervencion": "Estandarización del trabajo",
     "tipo": "no_digital", "brechas_aborda": [],
     "dimensiones_madurez": ["Procesos", "Personas"],
     "M_i_min": None, "recursos_requeridos": None,
     "costo_estimado": None, "estado_dato": ESTADO_PENDIENTE},

    {"id_intervencion": "I02", "intervencion": "Gestión visual",
     "tipo": "no_digital", "brechas_aborda": [],
     "dimensiones_madurez": ["Procesos", "Personas"],
     "M_i_min": None, "recursos_requeridos": None,
     "costo_estimado": None, "estado_dato": ESTADO_PENDIENTE},

    {"id_intervencion": "I03", "intervencion": "Reglas de liberación de órdenes",
     "tipo": "no_digital", "brechas_aborda": [],
     "dimensiones_madurez": ["Procesos", "Organización"],
     "M_i_min": None, "recursos_requeridos": None,
     "costo_estimado": None, "estado_dato": ESTADO_PENDIENTE},

    {"id_intervencion": "I04", "intervencion": "Mecanismos pull",
     "tipo": "no_digital", "brechas_aborda": [],
     "dimensiones_madurez": ["Procesos", "Organización"],
     "M_i_min": None, "recursos_requeridos": None,
     "costo_estimado": None, "estado_dato": ESTADO_PENDIENTE},

    {"id_intervencion": "I05", "intervencion": "Reducción de esperas",
     "tipo": "no_digital", "brechas_aborda": [],
     "dimensiones_madurez": ["Procesos", "Organización"],
     "M_i_min": None, "recursos_requeridos": None,
     "costo_estimado": None, "estado_dato": ESTADO_PENDIENTE},

    {"id_intervencion": "I06", "intervencion": "Mejoras de coordinación",
     "tipo": "no_digital", "brechas_aborda": [],
     "dimensiones_madurez": ["Personas", "Organización"],
     "M_i_min": None, "recursos_requeridos": None,
     "costo_estimado": None, "estado_dato": ESTADO_PENDIENTE},

    {"id_intervencion": "I07", "intervencion": "Captura automática de datos",
     "tipo": "digital", "brechas_aborda": [],
     "dimensiones_madurez": ["Tecnología", "Procesos"],
     "M_i_min": None, "recursos_requeridos": None,
     "costo_estimado": None, "estado_dato": ESTADO_PENDIENTE},

    {"id_intervencion": "I08", "intervencion": "Sensores",
     "tipo": "digital", "brechas_aborda": [],
     "dimensiones_madurez": ["Tecnología", "Procesos"],
     "M_i_min": None, "recursos_requeridos": None,
     "costo_estimado": None, "estado_dato": ESTADO_PENDIENTE},

    {"id_intervencion": "I09", "intervencion": "Microcontroladores",
     "tipo": "digital", "brechas_aborda": [],
     "dimensiones_madurez": ["Tecnología"],
     "M_i_min": None, "recursos_requeridos": None,
     "costo_estimado": None, "estado_dato": ESTADO_PENDIENTE},

    {"id_intervencion": "I10", "intervencion": "Tableros digitales",
     "tipo": "digital", "brechas_aborda": [],
     "dimensiones_madurez": ["Tecnología", "Procesos"],
     "M_i_min": None, "recursos_requeridos": None,
     "costo_estimado": None, "estado_dato": ESTADO_PENDIENTE}
]

# ============================================================
# 3. MAPEO BRECHA ↔ INTERVENCIÓN
# ============================================================

df_mapeo_brechas_intervenciones = pd.DataFrame(columns=[
    "brecha_C1",
    "brecha_C2",
    "id_intervencion",
    "intervencion",
    "dimension_madurez",
    "M_i_min",
    "estado_mapeo"
])

# ============================================================
# 4. VERIFICAR MADUREZ
# ============================================================

def verificar_madurez(intervencion, M_G):
    M_min = intervencion["M_i_min"]
    if intervencion["tipo"] == "no_digital":
        return True, "No requiere nivel mínimo de madurez digital"
    if M_min is None:
        return None, "M_i_min pendiente de validación"
    if M_G is None:
        return None, "M_G pendiente de cálculo"
    if M_G >= M_min:
        return True, "Cumple requisito de madurez"
    return False, "No cumple requisito de madurez"

# ============================================================
# 5. VERIFICAR RECURSOS
# ============================================================

def verificar_recursos(recursos_requeridos, recursos_disponibles):
    if recursos_requeridos is None or recursos_disponibles is None:
        return None, "Recursos pendientes de validación"
    return None, "Regla de comparación pendiente de parametrización"

# ============================================================
# 6. VERIFICAR PRESUPUESTO
# ============================================================

def verificar_presupuesto(costo, presupuesto_maximo):
    if costo is None or presupuesto_maximo is None:
        return None, "Presupuesto pendiente de validación"
    if costo <= presupuesto_maximo:
        return True, "Cumple restricción presupuestaria"
    return False, "Excede presupuesto disponible"

# ============================================================
# 7. EVALUAR FACTIBILIDAD
# ============================================================

def evaluar_factibilidad(intervencion, M_G,
                         recursos_disponibles=None,
                         presupuesto_maximo=None):

    resultado_madurez, just_madurez = verificar_madurez(
        intervencion, M_G
    )
    resultado_recursos, just_recursos = verificar_recursos(
        intervencion["recursos_requeridos"],
        recursos_disponibles
    )
    resultado_presupuesto, just_presupuesto = verificar_presupuesto(
        intervencion["costo_estimado"],
        presupuesto_maximo
    )

    resultados = [resultado_madurez, resultado_recursos, resultado_presupuesto]

    if False in resultados:
        factibilidad = "NO_FACTIBLE"
    elif None in resultados:
        factibilidad = "PENDIENTE_VALIDACION"
    else:
        factibilidad = "FACTIBLE"

    justificacion = "; ".join([
        just_madurez,
        just_recursos,
        just_presupuesto
    ])

    return factibilidad, justificacion

# ============================================================
# 8. MATRIZ FINAL DE SALIDA
# ============================================================

df_alternativas_cp5 = pd.DataFrame(columns=[
    "brecha_C1",
    "brecha_C2",
    "intervencion",
    "M_i_min",
    "recursos_requeridos",
    "factibilidad",
    "justificacion"
])

# ============================================================
# 9. FUNCIÓN PRINCIPAL DE CP5
# ============================================================

def construir_alternativas_cp5(
    df_brechas_c1,
    catalogo_intervenciones,
    M_G,
    recursos_disponibles=None,
    presupuesto_maximo=None
):

    resultados = []

    for _, brecha in df_brechas_c1.iterrows():
        categoria = brecha["tipo_brecha"]

        for intervencion in catalogo_intervenciones:

            if categoria not in intervencion["brechas_aborda"]:
                continue

            factibilidad, justificacion = evaluar_factibilidad(
                intervencion,
                M_G,
                recursos_disponibles,
                presupuesto_maximo
            )

            resultados.append({
                "brecha_C1": brecha["brecha"],
                "brecha_C2": None,
                "intervencion": intervencion["intervencion"],
                "M_i_min": intervencion["M_i_min"],
                "recursos_requeridos": intervencion["recursos_requeridos"],
                "factibilidad": factibilidad,
                "justificacion": justificacion
            })

    return pd.DataFrame(resultados)

# [Omitido] CP5: verificación de estructura (prints) — ver tesis_carrasco.py, líneas 1352-1384.


# ============================================================
# CP6 — IMPLEMENTACIÓN DE LA REGLA DE PRIORIZACIÓN
# ============================================================



# ============================================================
# 1. PESOS CONFIGURABLES (SIN VALORES DEFINITIVOS)
# ============================================================

pesos_priorizacion = {
    "w_F": None,
    "w_M": None,
    "w_L": None
}

def validar_pesos_priorizacion(pesos):
    valores = [pesos["w_F"], pesos["w_M"], pesos["w_L"]]
    if any(v is None for v in valores):
        return False, "PENDIENTE_VALIDACION"
    if any(v < 0 for v in valores):
        return False, "Los pesos no pueden ser negativos"
    if sum(valores) <= 0:
        return False, "La suma de pesos debe ser mayor que cero"
    return True, "VALIDADO"

# ============================================================
# 2. ESCALA COMÚN 1–5
# ============================================================

ESCALA_PRIORIZACION = {
    1: "Muy baja",
    2: "Baja",
    3: "Media",
    4: "Alta",
    5: "Muy alta"
}

# ============================================================
# 3. MATRIZ F_i (intervención × brecha C1)
# ============================================================

df_matriz_F = pd.DataFrame(columns=[
    "id_intervencion",
    "espera",
    "acumulacion",
    "capacidad",
    "coordinacion",
    "visibilidad",
    "liberacion"
])

def obtener_Fi(id_intervencion, brecha_C1, df_matriz_F):
    fila = df_matriz_F[df_matriz_F["id_intervencion"] == id_intervencion]
    if fila.empty:
        return None, "Intervención no encontrada"
    if brecha_C1 not in df_matriz_F.columns:
        return None, "Brecha C1 no reconocida en la matriz"
    valor = fila.iloc[0][brecha_C1]
    if pd.isna(valor):
        return None, "F_i pendiente de validación"
    if not 1 <= valor <= 5:
        return None, "F_i fuera de escala 1–5"
    return float(valor), "F_i validado"

# ============================================================
# 4. CÁLCULO DE M_i
# ============================================================

def calcular_Mi(tipo_intervencion, M_G, M_i_min):
    if tipo_intervencion == "no_digital":
        return 5, "No requiere nivel mínimo de madurez digital"
    if M_i_min is None:
        return None, "M_i_min pendiente de validación"
    if M_G is None:
        return None, "M_G pendiente de validación"
    if M_G >= M_i_min:
        return 5, "Cumple requisito de madurez"
    return 1, "No cumple requisito mínimo de madurez"

# ============================================================
# 5. CONTRIBUCIÓN L_i (CAMPO MANUAL)
# ============================================================

df_contribucion_L = pd.DataFrame(columns=[
    "id_intervencion",
    "L_i",
    "fuente",
    "justificacion",
    "estado_dato"
])

def validar_Li(valor):
    if pd.isna(valor):
        return False, "L_i pendiente de validación"
    if not 1 <= valor <= 5:
        return False, "L_i fuera de escala 1–5"
    return True, "L_i validado"

# ============================================================
# 6. FILTRO PREVIO AL CÁLCULO
# ============================================================

def filtrar_factibles(df_cp5):
    factibles = df_cp5[df_cp5["factibilidad"] == "FACTIBLE"].copy()
    pendientes = df_cp5[df_cp5["factibilidad"] == "PENDIENTE_VALIDACION"].copy()
    no_factibles = df_cp5[df_cp5["factibilidad"] == "NO_FACTIBLE"].copy()
    return factibles, pendientes, no_factibles

# ============================================================
# 7. CÁLCULO DE S_i
# ============================================================

def calcular_Si(F_i, M_i, L_i, pesos):
    if F_i is None or M_i is None or L_i is None:
        return None, "PENDIENTE_VALIDACION"
    if any(pesos[k] is None for k in ["w_F", "w_M", "w_L"]):
        return None, "PENDIENTE_VALIDACION"
    S_i = (pesos["w_F"] * F_i + pesos["w_M"] * M_i + pesos["w_L"] * L_i)
    return S_i, "CALCULADO"

# ============================================================
# 8. JUSTIFICACIÓN
# ============================================================

def generar_justificacion(F_i, M_i, L_i, pesos, intervencion):
    return (
        f"{intervencion}: "
        f"F_i={F_i}, M_i={M_i}, L_i={L_i}. "
        f"Combinación ponderada de los tres criterios."
    )

# ============================================================
# 9. ORDENAMIENTO (SIN DESEMPATE ARTIFICIAL)
# ============================================================

def ordenar_prioridades(df):
    return df.sort_values(by="S_i", ascending=False, kind="stable")

# ============================================================
# 10. FUNCIÓN INTEGRADA DE CP6
# ============================================================

def ejecutar_cp6(df_cp5, df_matriz_F, df_contribucion_L,
                 pesos_priorizacion, M_G):

    factibles, pendientes, no_factibles = filtrar_factibles(df_cp5)

    resultados = []

    for _, alternativa in factibles.iterrows():
        id_i = alternativa["id_intervencion"]
        brecha = alternativa["brecha_C1"]

        F_i, estado_F = obtener_Fi(id_i, brecha, df_matriz_F)

        tipo = alternativa.get("tipo_intervencion")
        M_i_min = alternativa.get("M_i_min")

        M_i, just_M = calcular_Mi(tipo, M_G, M_i_min)

        fila_L = df_contribucion_L[df_contribucion_L["id_intervencion"] == id_i]
        L_i = fila_L.iloc[0]["L_i"] if not fila_L.empty else None

        S_i, estado_S = calcular_Si(F_i, M_i, L_i, pesos_priorizacion)

        resultados.append({
            "id_intervencion": id_i,
            "intervencion": alternativa["intervencion"],
            "brecha_C1": brecha,
            "brecha_C2": alternativa.get("brecha_C2"),
            "F_i": F_i,
            "M_i": M_i,
            "L_i": L_i,
            "w_F": pesos_priorizacion["w_F"],
            "w_M": pesos_priorizacion["w_M"],
            "w_L": pesos_priorizacion["w_L"],
            "S_i": S_i,
            "estado_S": estado_S,
            "justificacion": just_M
        })

    df_resultado = pd.DataFrame(resultados)

    if not df_resultado.empty:
        df_resultado = df_resultado[df_resultado["S_i"].notna()]
        if not df_resultado.empty:
            df_resultado = ordenar_prioridades(df_resultado)
            df_resultado = df_resultado.reset_index(drop=True)
            df_resultado["prioridad"] = df_resultado.index + 1

    return df_resultado, pendientes, no_factibles

# ============================================================
# 11. TABLA FINAL VACÍA
# ============================================================

df_priorizacion = pd.DataFrame(columns=[
    "prioridad", "id_intervencion", "intervencion",
    "brecha_C1", "brecha_C2", "F_i", "M_i", "L_i",
    "w_F", "w_M", "w_L", "S_i", "justificacion"
])

# [Omitido] CP6: verificación de estructura (prints) y `!pip install simpy` — ver tesis_carrasco.py, líneas 1593-1628.


# ============================================================
# CP7 — MODELO DES AS-IS (ESTRUCTURA)
# ============================================================



# ============================================================
# 1. CATÁLOGO DE OPERACIONES
# ============================================================

df_operaciones = pd.DataFrame([
    {"id_operacion": "OP01", "operacion": "Recepcion_MTO", "tiempo_ciclo_min": None, "unidad_tiempo": "min", "tipo_tiempo": ESTADO_PENDIENTE},
    {"id_operacion": "OP02", "operacion": "Diseno", "tiempo_ciclo_min": None, "unidad_tiempo": "min", "tipo_tiempo": ESTADO_PENDIENTE},
    {"id_operacion": "OP03", "operacion": "Corte_Punzonado", "tiempo_ciclo_min": 45, "unidad_tiempo": "min/lote_estandar", "tipo_tiempo": "CONFIRMADO"},
    {"id_operacion": "OP04", "operacion": "Plegado", "tiempo_ciclo_min": None, "unidad_tiempo": "min", "tipo_tiempo": ESTADO_PENDIENTE},
    {"id_operacion": "OP05", "operacion": "Soldadura", "tiempo_ciclo_min": 180, "unidad_tiempo": "min/lote_estandar", "tipo_tiempo": "CONFIRMADO"},
    {"id_operacion": "OP06", "operacion": "Armado", "tiempo_ciclo_min": 180, "unidad_tiempo": "min/lote_estandar", "tipo_tiempo": "CONFIRMADO"},
    {"id_operacion": "OP07", "operacion": "Acabado_superficial", "tiempo_ciclo_min": None, "unidad_tiempo": "min", "tipo_tiempo": ESTADO_PENDIENTE},
    {"id_operacion": "OP08", "operacion": "Pintura", "tiempo_ciclo_min": None, "unidad_tiempo": "min", "tipo_tiempo": ESTADO_PENDIENTE},
    {"id_operacion": "OP09", "operacion": "Inspeccion_final", "tiempo_ciclo_min": None, "unidad_tiempo": "min", "tipo_tiempo": ESTADO_PENDIENTE},
    {"id_operacion": "OP10", "operacion": "Despacho", "tiempo_ciclo_min": None, "unidad_tiempo": "min", "tipo_tiempo": ESTADO_PENDIENTE}
])

# ============================================================
# 2. RECURSOS (TODOS PENDIENTES)
# ============================================================

df_recursos_cp7 = pd.DataFrame([
    {"operacion": op, "operarios": None, "maquinas": None,
     "disponibilidad": None, "turnos": None, "horas_por_turno": None,
     "estado_dato": ESTADO_PENDIENTE}
    for op in df_operaciones["operacion"]
])

# ============================================================
# 3. TIEMPOS ADICIONALES (PENDIENTES)
# ============================================================

df_tiempos_adicionales = pd.DataFrame([
    {"operacion": op, "espera_min": None, "setup_min": None, "traslado_min": None,
     "estado_espera": ESTADO_PENDIENTE, "estado_setup": ESTADO_PENDIENTE,
     "estado_traslado": ESTADO_PENDIENTE}
    for op in df_operaciones["operacion"]
])

# ============================================================
# 4. RUTAS PARAMETRIZABLES
# ============================================================

df_rutas = pd.DataFrame([
    {
        "producto": "PRODUCTO_BASE",
        "ruta": [
            "Recepcion_MTO", "Diseno", "Corte_Punzonado", "Plegado",
            "Soldadura", "Armado", "Acabado_superficial", "Pintura",
            "Inspeccion_final", "Despacho"
        ],
        "pintura_aplica": True,
        "estado_dato": "BASE_PARAMETRIZABLE"
    }
])

# ============================================================
# 5. PARÁMETROS DE LLEGADAS (PENDIENTES)
# ============================================================

param_llegadas = {
    "distribucion": None,
    "parametros": None,
    "frecuencia": None,
    "periodo_analisis": None,
    "prueba_bondad_ajuste": None,
    "estado_dato": ESTADO_PENDIENTE
}

# ============================================================
# 6. ESTRUCTURA DE ORDEN MTO
# ============================================================

def crear_orden(id_orden=None, producto=None, ruta=None):
    return {
        "id_orden": id_orden,
        "producto": producto,
        "fecha_hora_llegada": None,
        "fecha_hora_salida": None,
        "ruta": ruta,
        "estado": "pendiente",
        "tiempo_proceso_total_min": 0,
        "tiempo_espera_total_min": 0,
        "tiempo_setup_total_min": 0,
        "tiempo_traslado_total_min": 0,
        "lead_time_min": None
    }

# ============================================================
# 7. OBTENER TIEMPO DE PROCESO
# ============================================================

def obtener_tiempo_proceso(operacion, parametros_lote=None):
    fila = df_operaciones[df_operaciones["operacion"] == operacion]
    if fila.empty:
        raise ValueError(f"Operación no encontrada: {operacion}")
    tiempo = fila.iloc[0]["tiempo_ciclo_min"]
    unidad = fila.iloc[0]["unidad_tiempo"]
    if pd.isna(tiempo):
        return None
    if unidad == "min/lote_estandar":
        if parametros_lote is None:
            raise ValueError("Falta definir la relación entre orden y lote estándar.")
    return tiempo

# ============================================================
# 8. WIP POR ESTACIÓN
# ============================================================

wip_por_operacion = {op: 0 for op in df_operaciones["operacion"]}

# ============================================================
# 9. CONSERVACIÓN DE ENTIDADES
# ============================================================

registro_entidades = {
    "ordenes_llegadas": 0,
    "ordenes_despachadas": 0,
    "ordenes_en_proceso": 0
}

def verificar_conservacion(registro):
    total = registro["ordenes_despachadas"] + registro["ordenes_en_proceso"]
    return total == registro["ordenes_llegadas"]

# ============================================================
# 10. VALIDACIÓN PREVIA
# ============================================================

def validar_parametros_cp7():
    pendientes = []
    if param_llegadas["distribucion"] is None:
        pendientes.append("Distribución de llegadas")
    for _, fila in df_operaciones.iterrows():
        if pd.isna(fila["tiempo_ciclo_min"]):
            pendientes.append(f"Tiempo de proceso: {fila['operacion']}")
    for _, fila in df_recursos_cp7.iterrows():
        if fila["operarios"] is None:
            pendientes.append(f"Operarios: {fila['operacion']}")
        if fila["maquinas"] is None:
            pendientes.append(f"Máquinas: {fila['operacion']}")
    return pendientes

# [Omitido] CP7: verificación de estructura (prints) — ver tesis_carrasco.py, líneas 1783-1814.


# ============================================================
# CP8 — CALIBRACIÓN DEL MODELO DES AS-IS
# ============================================================



# ============================================================
# 1. ESTADOS DE CALIBRACIÓN
# ============================================================

ESTADOS_CALIBRACION = {
    "PENDIENTE": "Dato real aún no disponible",
    "CARGADO": "Dato real incorporado al modelo",
    "AJUSTADO": "Parámetro actualizado con evidencia",
    "VALIDADO": "Modelo cumple criterios establecidos"
}

# ============================================================
# 2. PARÁMETROS CALIBRABLES
# ============================================================

parametros_calibrables = [
    "distribucion_llegadas",
    "tiempos_proceso",
    "tiempos_espera",
    "tiempos_setup",
    "tiempos_traslado",
    "numero_operarios",
    "numero_maquinas",
    "disponibilidad_recursos",
    "turnos",
    "horas_por_turno",
    "rutas_producto",
    "tamano_lote_estandar"
]

# ============================================================
# 3. REGISTRO DE TRAZABILIDAD
# ============================================================

df_trazabilidad_calibracion = pd.DataFrame(columns=[
    "parametro",
    "valor_anterior",
    "valor_nuevo",
    "fuente_dato",
    "justificacion_ajuste",
    "indicador_afectado",
    "fecha_estado"
])

# ============================================================
# 4. DATOS DE REFERENCIA (CONTRASTE, NO ENTRADA)
# ============================================================

referencias_reales = {
    "LT_dias": 24.5,
    "WIP_ordenes": 18,
    "PCE_porcentaje": 8.5,
    "pedidos_fuera_fecha_porcentaje": 42.0
}

# ============================================================
# 5. CONFIGURACIÓN TEMPORAL
# ============================================================

config_tiempo = {
    "unidad_LT_referencia": "dias_habiles",
    "unidad_simulacion": "minutos",
    "horas_por_dia": None,
    "dias_habiles_por_semana": None,
    "estado": ESTADO_PENDIENTE
}

# ============================================================
# 6. COMPARACIÓN DE INDICADORES
# ============================================================

def comparar_indicadores(LT_sim=None, WIP_sim=None, PCE_sim=None):
    return {
        "LT_real": 24.5,
        "LT_sim": LT_sim,
        "WIP_real": 18,
        "WIP_sim": WIP_sim,
        "PCE_real": 8.5,
        "PCE_sim": PCE_sim
    }

def calcular_diferencias(LT_sim=None, WIP_sim=None, PCE_sim=None):
    return {
        "error_LT": (LT_sim - 24.5) if LT_sim is not None else None,
        "error_WIP": (WIP_sim - 18) if WIP_sim is not None else None,
        "error_PCE": (PCE_sim - 8.5) if PCE_sim is not None else None
    }

# ============================================================
# 7. CRITERIOS DE ACEPTACIÓN (TOLERANCIAS PENDIENTES)
# ============================================================

criterios_aceptacion = {
    "LT": {"valor_real": 24.5, "tolerancia": None, "estado": "PENDIENTE_VALIDACION_METODOLOGICA"},
    "WIP": {"valor_real": 18, "tolerancia": None, "estado": "PENDIENTE_VALIDACION_METODOLOGICA"},
    "PCE": {"valor_real": 8.5, "tolerancia": None, "estado": "PENDIENTE_VALIDACION_METODOLOGICA"}
}

# ============================================================
# 8. REGISTRAR AJUSTE
# ============================================================

def registrar_ajuste(parametro, valor_anterior, valor_nuevo,
                     fuente_dato, justificacion_ajuste,
                     indicador_afectado, estado="AJUSTADO"):
    nuevo_registro = pd.DataFrame([{
        "parametro": parametro,
        "valor_anterior": valor_anterior,
        "valor_nuevo": valor_nuevo,
        "fuente_dato": fuente_dato,
        "justificacion_ajuste": justificacion_ajuste,
        "indicador_afectado": indicador_afectado,
        "fecha_estado": datetime.now().strftime("%Y-%m-%d")
    }])
    return nuevo_registro

# ============================================================
# 9. REGLA PARA EVITAR CALIBRACIÓN ARTIFICIAL
# ============================================================

def permitir_ajuste(fuente_dato, justificacion_ajuste, valor_nuevo):
    if fuente_dato is None:
        return False
    if justificacion_ajuste is None:
        return False
    if valor_nuevo is None:
        return False
    return True

# [Omitido] CP8: verificación de estructura (prints) — ver tesis_carrasco.py, líneas 1955-1997.


# ============================================================
# CP9 — CONSTRUCCIÓN DE ESCENARIOS TO-BE
# ============================================================


# ============================================================
# 1. FILTRO DE INTERVENCIONES EJECUTABLES
# ============================================================

def obtener_intervenciones_ejecutables(df_cp6):
    if df_cp6 is None or df_cp6.empty:
        return pd.DataFrame(), pd.DataFrame()

    requeridas = ["id_intervencion", "intervencion", "factibilidad", "S_i"]
    faltantes = [c for c in requeridas if c not in df_cp6.columns]

    if faltantes:
        raise ValueError(f"Faltan columnas requeridas de CP6: {faltantes}")

    ejecutables = df_cp6[
        (df_cp6["factibilidad"] == "FACTIBLE") &
        (df_cp6["S_i"].notna())
    ].copy()

    no_ejecutables = df_cp6[
        ~((df_cp6["factibilidad"] == "FACTIBLE") & (df_cp6["S_i"].notna()))
    ].copy()

    return ejecutables, no_ejecutables

# ============================================================
# 2. CATÁLOGO DE ESCENARIOS
# ============================================================

catalogo_escenarios = {
    "I01": "S01_Estandarizacion",
    "I02": "S02_Gestion_Visual",
    "I03": "S03_Reglas_Liberacion",
    "I04": "S04_Mecanismos_Pull",
    "I05": "S05_Reduccion_Esperas",
    "I06": "S06_Mejoras_Coordinacion",
    "I07": "S07_Captura_Automatica",
    "I08": "S08_Sensores",
    "I09": "S09_Microcontroladores",
    "I10": "S10_Tableros_Digitales"
}

# ============================================================
# 3. MAPEO INTERVENCIÓN → VARIABLE DES
# ============================================================

mapeo_intervenciones = {
    "I01": {
        "escenario": "S01_Estandarizacion",
        "variables": ["tiempo_proceso", "variabilidad_tiempo_proceso"],
        "justificacion_base": "La estandarización puede modificar el tiempo de proceso y/o su variabilidad; el efecto debe determinarse mediante evidencia."
    },
    "I02": {
        "escenario": "S02_Gestion_Visual",
        "variables": ["tiempo_espera", "tiempo_coordinacion"],
        "justificacion_base": "La gestión visual puede reducir esperas o problemas de coordinación; el efecto debe sustentarse con evidencia."
    },
    "I03": {
        "escenario": "S03_Reglas_Liberacion",
        "variables": ["logica_liberacion_ordenes", "entrada_ordenes"],
        "justificacion_base": "Las reglas de liberación modifican la lógica con la que las órdenes ingresan al sistema."
    },
    "I04": {
        "escenario": "S04_Mecanismos_Pull",
        "variables": ["regla_reposicion", "logica_liberacion"],
        "justificacion_base": "El mecanismo pull modifica las reglas de reposición y/o liberación de órdenes."
    },
    "I05": {
        "escenario": "S05_Reduccion_Esperas",
        "variables": ["tiempo_espera"],
        "justificacion_base": "La intervención actúa directamente sobre los tiempos de espera identificados en el flujo."
    },
    "I06": {
        "escenario": "S06_Mejoras_Coordinacion",
        "variables": ["tiempo_espera", "tiempo_coordinacion", "logica_coordinacion"],
        "justificacion_base": "La coordinación puede afectar esperas y la secuencia de atención entre operaciones."
    },
    "I07": {
        "escenario": "S07_Captura_Automatica",
        "variables": ["tiempo_captura_datos", "disponibilidad_informacion"],
        "justificacion_base": "La captura automática representa un habilitador digital cuya aplicación depende de madurez y recursos."
    },
    "I08": {
        "escenario": "S08_Sensores",
        "variables": ["disponibilidad_informacion", "tiempo_captura_datos"],
        "justificacion_base": "Los sensores representan un habilitador digital sujeto a factibilidad tecnológica y organizacional."
    },
    "I09": {
        "escenario": "S09_Microcontroladores",
        "variables": ["disponibilidad_informacion", "tiempo_captura_datos"],
        "justificacion_base": "Los microcontroladores constituyen un habilitador digital sujeto a madurez y recursos."
    },
    "I10": {
        "escenario": "S10_Tableros_Digitales",
        "variables": ["disponibilidad_informacion", "tiempo_coordinacion", "tiempo_espera"],
        "justificacion_base": "Los tableros digitales pueden modificar la disponibilidad y comunicación de información."
    }
}

# ============================================================
# 4. ESTRUCTURA DE MODIFICACIONES TO-BE
# ============================================================

df_modificaciones_tobe = pd.DataFrame(columns=[
    "id_escenario", "id_intervencion", "intervencion",
    "variable_objetivo", "valor_actual", "valor_nuevo",
    "fuente_evidencia", "justificacion", "estado", "observaciones"
])

ESTADOS_TOBE = {"PENDIENTE_CONFIRMAR", "CONFIRMADO"}

# ============================================================
# 5. GENERADOR DE ESCENARIOS TO-BE
# ============================================================

def construir_escenarios_tobe(df_cp6):
    ejecutables, no_ejecutables = obtener_intervenciones_ejecutables(df_cp6)
    registros = []

    for _, fila in ejecutables.iterrows():
        id_intervencion = fila["id_intervencion"]

        if id_intervencion not in mapeo_intervenciones:
            continue

        config = mapeo_intervenciones[id_intervencion]

        for variable in config["variables"]:
            registros.append({
                "id_escenario": config["escenario"],
                "id_intervencion": id_intervencion,
                "intervencion": fila["intervencion"],
                "variable_objetivo": variable,
                "valor_actual": None,
                "valor_nuevo": None,
                "fuente_evidencia": None,
                "justificacion": config["justificacion_base"],
                "estado": "PENDIENTE_CONFIRMAR",
                "observaciones": "Requiere evidencia real antes de ejecutar."
            })

    df_escenarios = pd.DataFrame(registros)
    return df_escenarios, no_ejecutables

# ============================================================
# 6. HABILITADOR DIGITAL EJECUTABLE
# ============================================================

def habilitador_digital_ejecutable(MG, Mi_min, recursos_ok, presupuesto_ok):
    if MG is None or Mi_min is None:
        return False
    if recursos_ok is None or presupuesto_ok is None:
        return False
    return (MG >= Mi_min and recursos_ok and presupuesto_ok)

# ============================================================
# 7. OBJETIVOS TO-BE (SOLO PARA EVALUACIÓN POSTERIOR)
# ============================================================

objetivos_tobe = {
    "LT_max_dias": 14,
    "WIP_max_ordenes": 6,
    "PCE_min_porcentaje": 20
}

# [Omitido] CP9: verificación de estructura (prints) — ver tesis_carrasco.py, líneas 2171-2204.


# ============================================================
# CP10 — SIMULACIÓN CON MÚLTIPLES RÉPLICAS
# ============================================================


# ============================================================
# 1. PARÁMETROS DE SIMULACIÓN (PENDIENTES)
# ============================================================

parametros_simulacion = {
    "warm_up": None,
    "longitud_corrida": None,
    "num_replicas": None,
    "estado": "PENDIENTE_VALIDACION"
}

def validar_parametros_simulacion(parametros):
    pendientes = []
    if parametros["warm_up"] is None:
        pendientes.append("warm_up")
    if parametros["longitud_corrida"] is None:
        pendientes.append("longitud_corrida")
    if parametros["num_replicas"] is None:
        pendientes.append("num_replicas")

    if pendientes:
        return False, (
            "Ejecución bloqueada: parámetros de simulación "
            "pendientes de validación metodológica."
        )
    return True, "Parámetros completos."

# ============================================================
# 2. SEMILLAS ALEATORIAS
# ============================================================

def generar_semillas(num_replicas, semilla_base=None):
    if num_replicas is None:
        return []
    if semilla_base is None:
        raise ValueError("La semilla base debe definirse para garantizar trazabilidad.")
    return [semilla_base + i for i in range(num_replicas)]

# ============================================================
# 3. DATAFRAME DE RÉPLICAS
# ============================================================

df_replicas = pd.DataFrame(columns=[
    "id_escenario", "replica", "semilla",
    "warm_up", "longitud_corrida", "condicion_inicial",
    "LT", "WIP", "PCE", "estado"
])

# ============================================================
# 4. CONFIGURACIONES INICIALES (PENDIENTES)
# ============================================================

configuraciones_iniciales = {
    "sistema_vacio": {
        "WIP_inicial": 0,
        "fuente": None,
        "estado_dato": "PENDIENTE_VALIDACION"
    },
    "estado_representativo": {
        "WIP_inicial": None,
        "fuente": None,
        "estado_dato": "PENDIENTE_VALIDACION"
    }
}

def configurar_estado_inicial(nombre_configuracion):
    if nombre_configuracion not in configuraciones_iniciales:
        raise ValueError(f"Configuración no reconocida: {nombre_configuracion}")
    config = configuraciones_iniciales[nombre_configuracion]
    if config["WIP_inicial"] is None:
        raise ValueError("El WIP inicial de esta configuración continúa pendiente de datos reales.")
    return config

# ============================================================
# 5. EJECUCIÓN DE UNA RÉPLICA
# ============================================================

def ejecutar_replica(escenario, replica, semilla,
                     parametros_simulacion, configuracion_inicial):
    valido, mensaje = validar_parametros_simulacion(parametros_simulacion)
    if not valido:
        raise RuntimeError(mensaje)

    estado_inicial = configurar_estado_inicial(configuracion_inicial)

    resultado = {
        "id_escenario": escenario,
        "replica": replica,
        "semilla": semilla,
        "warm_up": parametros_simulacion["warm_up"],
        "longitud_corrida": parametros_simulacion["longitud_corrida"],
        "condicion_inicial": configuracion_inicial,
        "LT": None,
        "WIP": None,
        "PCE": None,
        "estado": "PENDIENTE_EJECUCION"
    }
    return resultado

# ============================================================
# 6. EJECUCIÓN DE MÚLTIPLES RÉPLICAS
# ============================================================

def ejecutar_replicas(escenario, parametros_simulacion,
                      configuracion_inicial, semilla_base=None):
    valido, mensaje = validar_parametros_simulacion(parametros_simulacion)
    if not valido:
        return {
            "estado": "BLOQUEADO",
            "mensaje": mensaje,
            "resultados": pd.DataFrame()
        }

    num_replicas = parametros_simulacion["num_replicas"]
    semillas = generar_semillas(num_replicas, semilla_base)

    resultados = []
    for i, semilla in enumerate(semillas, start=1):
        resultado = ejecutar_replica(
            escenario=escenario, replica=i, semilla=semilla,
            parametros_simulacion=parametros_simulacion,
            configuracion_inicial=configuracion_inicial
        )
        resultados.append(resultado)

    return {
        "estado": "EJECUTADO",
        "mensaje": "Réplicas generadas.",
        "resultados": pd.DataFrame(resultados)
    }

# ============================================================
# 7. VERIFICAR ESTOCASTICIDAD
# ============================================================

componentes_estocasticos = {
    "llegadas": False,
    "tiempo_proceso": False,
    "tiempo_espera": False
}

def verificar_estocasticidad(componentes):
    return any(componentes.values())

# ============================================================
# 8. ESTADÍSTICOS POR ESCENARIO
# ============================================================

def calcular_estadisticos(resultados_replicas):
    if resultados_replicas.empty:
        return {
            "media": None,
            "desviacion_estandar": None,
            "intervalo_confianza": None,
            "minimo": None,
            "maximo": None,
            "num_replicas": 0
        }

    resultados = resultados_replicas[["LT", "WIP", "PCE"]]

    return {
        "media": resultados.mean(),
        "desviacion_estandar": resultados.std(ddof=1),
        "intervalo_confianza": None,
        "minimo": resultados.min(),
        "maximo": resultados.max(),
        "num_replicas": len(resultados)
    }

# ============================================================
# 9. INTERVALO DE CONFIANZA (PENDIENTE)
# ============================================================

def calcular_intervalo_confianza(resultados, metodo=None, nivel_confianza=None):
    if metodo is None:
        return None
    if nivel_confianza is None:
        return None
    return None

metodos_intervalo = {
    "t_student": None,
    "normal": None,
    "bootstrap": None,
    "estado_seleccion": "PENDIENTE_VALIDACION"
}

# ============================================================
# 10. TABLA RESUMEN
# ============================================================

df_resumen_escenarios = pd.DataFrame(columns=[
    "escenario",
    "LT_media", "LT_desv_std", "LT_IC", "LT_min", "LT_max",
    "WIP_media", "WIP_desv_std", "WIP_IC", "WIP_min", "WIP_max",
    "PCE_media", "PCE_desv_std", "PCE_IC", "PCE_min", "PCE_max",
    "num_replicas", "metodo_estadistico", "estado"
])

# ============================================================
# 11. COMPARACIÓN AS-IS vs. TO-BE
# ============================================================

metodos_comparacion_candidatos = {
    "t_test_pareado": None,
    "t_test_independiente": None,
    "mann_whitney": None,
    "anova": None,
    "bootstrap": None,
    "estado_seleccion": "PENDIENTE_VALIDACION"
}

def diferencia_escenarios(media_as_is, media_to_be):
    if media_as_is is None or media_to_be is None:
        return None
    return media_to_be - media_as_is

# ============================================================
# 12. FUNCIÓN PRINCIPAL DE CP10
# ============================================================

def ejecutar_cp10(escenario, parametros_simulacion,
                  configuracion_inicial, semilla_base=None):
    valido, mensaje = validar_parametros_simulacion(parametros_simulacion)
    if not valido:
        return {
            "estado": "BLOQUEADO",
            "mensaje": "Ejecución bloqueada: parámetros de simulación pendientes de validación metodológica.",
            "resultados": None
        }
    return ejecutar_replicas(
        escenario=escenario,
        parametros_simulacion=parametros_simulacion,
        configuracion_inicial=configuracion_inicial,
        semilla_base=semilla_base
    )

# [Omitido] CP10: verificación de estructura (prints) — ver tesis_carrasco.py, líneas 2451-2496.


# ============================================================
# CP11 — EVALUACIÓN DE ESCENARIOS
# ============================================================


# ============================================================
# 1. METAS PRELIMINARES TO-BE
# ============================================================

METAS_TOBE = {
    "LT_max": 14.0,
    "WIP_max": 6.0,
    "PCE_min": 20.0
}

# ============================================================
# 2. ESTADOS
# ============================================================

ESTADOS_METAS = ["CUMPLE_METAS", "CUMPLE_PARCIALMENTE", "NO_CUMPLE", "PENDIENTE_DATOS"]
ESTADOS_RESTRICCIONES = ["CUMPLE", "NO_CUMPLE", "PENDIENTE_VALIDACION"]

# ============================================================
# 3. VALIDACIÓN DE DATAFRAMES
# ============================================================

def validar_dataframe_replicas(df, nombre_df):
    if df is None:
        return {"estado": "PENDIENTE_DATOS", "mensaje": f"{nombre_df} es None."}
    if not isinstance(df, pd.DataFrame):
        return {"estado": "PENDIENTE_DATOS", "mensaje": f"{nombre_df} no es un DataFrame."}
    if df.empty:
        return {"estado": "PENDIENTE_DATOS", "mensaje": f"{nombre_df} está vacío."}
    columnas_requeridas = ["LT", "WIP", "PCE"]
    faltantes = [c for c in columnas_requeridas if c not in df.columns]
    if faltantes:
        return {"estado": "PENDIENTE_DATOS", "mensaje": f"{nombre_df} no contiene: {faltantes}"}
    return {"estado": "OK", "mensaje": f"{nombre_df} disponible."}

# ============================================================
# 4. OBTENER MEDIA
# ============================================================

def obtener_media(df, indicador):
    validacion = validar_dataframe_replicas(df, "DataFrame de réplicas")
    if validacion["estado"] != "OK":
        return None
    valores = pd.to_numeric(df[indicador], errors="coerce").dropna()
    if valores.empty:
        return None
    return valores.mean()

# ============================================================
# 5. VARIACIÓN PORCENTUAL
# ============================================================

def calcular_variacion_porcentual(valor_asis, valor_tobe):
    if valor_asis is None or valor_tobe is None:
        return None
    if pd.isna(valor_asis) or pd.isna(valor_tobe):
        return None
    if valor_asis == 0:
        return None
    return ((valor_tobe - valor_asis) / valor_asis) * 100

# ============================================================
# 6. EVALUAR METAS
# ============================================================

def evaluar_metas(valor_lt, valor_wip, valor_pce):
    if any(v is None or pd.isna(v) for v in [valor_lt, valor_wip, valor_pce]):
        return {"cumple_LT": None, "cumple_WIP": None, "cumple_PCE": None, "estado_metas": "PENDIENTE_DATOS"}

    cumple_lt = valor_lt <= METAS_TOBE["LT_max"]
    cumple_wip = valor_wip <= METAS_TOBE["WIP_max"]
    cumple_pce = valor_pce > METAS_TOBE["PCE_min"]

    cantidad_cumplida = sum([cumple_lt, cumple_wip, cumple_pce])

    if cantidad_cumplida == 3:
        estado = "CUMPLE_METAS"
    elif cantidad_cumplida > 0:
        estado = "CUMPLE_PARCIALMENTE"
    else:
        estado = "NO_CUMPLE"

    return {"cumple_LT": cumple_lt, "cumple_WIP": cumple_wip, "cumple_PCE": cumple_pce, "estado_metas": estado}

# ============================================================
# 7. OBJETIVO GENERAL: MIN LT
# ============================================================

def evaluar_objetivo_lt(lt_asis, lt_tobe):
    if lt_asis is None or lt_tobe is None:
        return None
    if pd.isna(lt_asis) or pd.isna(lt_tobe):
        return None
    return lt_tobe < lt_asis

# ============================================================
# 8. RESTRICCIONES
# ============================================================

def evaluar_recursos(R_i, R_disponible):
    if R_i is None or R_disponible is None:
        return "PENDIENTE_VALIDACION"
    if pd.isna(R_i) or pd.isna(R_disponible):
        return "PENDIENTE_VALIDACION"
    return "CUMPLE" if R_i <= R_disponible else "NO_CUMPLE"

def evaluar_presupuesto(C_i, B_max):
    if C_i is None or B_max is None:
        return "PENDIENTE_VALIDACION"
    if pd.isna(C_i) or pd.isna(B_max):
        return "PENDIENTE_VALIDACION"
    return "CUMPLE" if C_i <= B_max else "NO_CUMPLE"

def evaluar_madurez(M_G, M_i_min, es_digital):
    if not es_digital:
        return "CUMPLE"
    if M_G is None or M_i_min is None:
        return "PENDIENTE_VALIDACION"
    if pd.isna(M_G) or pd.isna(M_i_min):
        return "PENDIENTE_VALIDACION"
    return "CUMPLE" if M_G >= M_i_min else "NO_CUMPLE"

def evaluar_restricciones(R_i, R_disponible, C_i, B_max, M_G, M_i_min, es_digital):
    estado_recursos = evaluar_recursos(R_i, R_disponible)
    estado_presupuesto = evaluar_presupuesto(C_i, B_max)
    estado_madurez = evaluar_madurez(M_G, M_i_min, es_digital)

    estados = [estado_recursos, estado_presupuesto, estado_madurez]

    if "NO_CUMPLE" in estados:
        estado_general = "NO_CUMPLE"
    elif "PENDIENTE_VALIDACION" in estados:
        estado_general = "PENDIENTE_VALIDACION"
    else:
        estado_general = "CUMPLE"

    return {
        "restriccion_recursos": estado_recursos,
        "restriccion_presupuesto": estado_presupuesto,
        "restriccion_madurez": estado_madurez,
        "estado_restricciones": estado_general
    }

# ============================================================
# 9. EVALUACIÓN COMPLETA DE UN ESCENARIO
# ============================================================

def evaluar_escenario(id_escenario, intervencion, df_asis, df_tobe,
                      R_i=None, R_disponible=None, C_i=None, B_max=None,
                      M_G=None, M_i_min=None, es_digital=False):

    lt_asis = obtener_media(df_asis, "LT")
    wip_asis = obtener_media(df_asis, "WIP")
    pce_asis = obtener_media(df_asis, "PCE")

    lt_tobe = obtener_media(df_tobe, "LT")
    wip_tobe = obtener_media(df_tobe, "WIP")
    pce_tobe = obtener_media(df_tobe, "PCE")

    delta_lt = calcular_variacion_porcentual(lt_asis, lt_tobe)
    delta_wip = calcular_variacion_porcentual(wip_asis, wip_tobe)
    delta_pce = calcular_variacion_porcentual(pce_asis, pce_tobe)

    objetivo_min_lt = evaluar_objetivo_lt(lt_asis, lt_tobe)
    evaluacion_metas = evaluar_metas(lt_tobe, wip_tobe, pce_tobe)
    eval_restricciones = evaluar_restricciones(R_i, R_disponible, C_i, B_max, M_G, M_i_min, es_digital)

    datos_simulacion_disponibles = all([lt_tobe is not None, wip_tobe is not None, pce_tobe is not None])

    if not datos_simulacion_disponibles:
        estado_final = "PENDIENTE_DATOS"
    elif evaluacion_metas["estado_metas"] == "CUMPLE_METAS" and eval_restricciones["estado_restricciones"] == "CUMPLE":
        estado_final = "CUMPLE"
    elif eval_restricciones["estado_restricciones"] == "NO_CUMPLE":
        estado_final = "NO_CUMPLE"
    elif eval_restricciones["estado_restricciones"] == "PENDIENTE_VALIDACION":
        estado_final = "PENDIENTE_VALIDACION"
    else:
        estado_final = evaluacion_metas["estado_metas"]

    return {
        "id_escenario": id_escenario,
        "intervencion": intervencion,
        "LT_ASIS": lt_asis, "WIP_ASIS": wip_asis, "PCE_ASIS": pce_asis,
        "LT_TOBE": lt_tobe, "WIP_TOBE": wip_tobe, "PCE_TOBE": pce_tobe,
        "delta_LT_pct": delta_lt, "delta_WIP_pct": delta_wip, "delta_PCE_pct": delta_pce,
        "min_LT_vs_ASIS": objetivo_min_lt,
        "cumple_LT_14": evaluacion_metas["cumple_LT"],
        "cumple_WIP_6": evaluacion_metas["cumple_WIP"],
        "cumple_PCE_20": evaluacion_metas["cumple_PCE"],
        "estado_metas": evaluacion_metas["estado_metas"],
        "restriccion_recursos": eval_restricciones["restriccion_recursos"],
        "restriccion_presupuesto": eval_restricciones["restriccion_presupuesto"],
        "restriccion_madurez": eval_restricciones["restriccion_madurez"],
        "estado_restricciones": eval_restricciones["estado_restricciones"],
        "estado_final": estado_final
    }

# ============================================================
# 10. EVALUACIÓN DE MÚLTIPLES ESCENARIOS
# ============================================================

def evaluar_escenarios(df_replicas_asis, escenarios):
    resultados = []

    if df_replicas_asis is None or df_replicas_asis.empty:
        for escenario in escenarios:
            resultados.append({
                "id_escenario": escenario.get("id_escenario"),
                "intervencion": escenario.get("intervencion"),
                "estado_final": "PENDIENTE_DATOS"
            })
        return pd.DataFrame(resultados)

    for escenario in escenarios:
        resultado = evaluar_escenario(
            id_escenario=escenario.get("id_escenario"),
            intervencion=escenario.get("intervencion"),
            df_asis=df_replicas_asis,
            df_tobe=escenario.get("df_replicas_tobe"),
            R_i=escenario.get("R_i"),
            R_disponible=escenario.get("R_disponible"),
            C_i=escenario.get("C_i"),
            B_max=escenario.get("B_max"),
            M_G=escenario.get("M_G"),
            M_i_min=escenario.get("M_i_min"),
            es_digital=escenario.get("es_digital", False)
        )
        resultados.append(resultado)

    return pd.DataFrame(resultados)

# [Omitido] CP11: verificación de estructura (prints) — ver tesis_carrasco.py, líneas 2736-2773.


# ============================================================
# CP12 — INTEGRACIÓN DEL DSS
# ============================================================


ESTADO_OK = "OK"
ESTADO_PENDIENTE_DSS = "PENDIENTE_DATOS"
ESTADO_VALIDACION = "PENDIENTE_VALIDACION"

# ============================================================
# 1. ESTRUCTURA GENERAL DE ENTRADA
# ============================================================

def crear_entrada_dss(
    df_ordenes=None, df_procesos=None, df_recursos=None,
    df_madurez=None, df_simulacion=None,
    df_rutas_orden=None, df_vsm=None, df_indicadores_vsm=None,
    df_carga_capacidad=None,
    df_madurez_respuestas=None,
    df_mapeo_brechas_intervenciones=None, df_alternativas_cp5=None,
    df_priorizacion=None, df_matriz_F=None, df_contribucion_L=None,
    df_operaciones=None, df_rutas=None, param_llegadas=None,
    df_trazabilidad_calibracion=None, criterios_aceptacion=None,
    df_modificaciones_tobe=None, catalogo_escenarios=None,
    df_replicas=None, df_resumen_escenarios=None, parametros_simulacion=None,
    df_evaluacion_cp11=None, METAS_TOBE=None
):
    return {
        "CP1": {"df_ordenes": df_ordenes, "df_procesos": df_procesos,
                "df_recursos": df_recursos, "df_madurez": df_madurez,
                "df_simulacion": df_simulacion},
        "CP2": {"df_rutas_orden": df_rutas_orden, "df_vsm": df_vsm,
                "df_indicadores_vsm": df_indicadores_vsm},
        "CP3": {"df_carga_capacidad": df_carga_capacidad},
        "CP4": {"df_madurez_respuestas": df_madurez_respuestas},
        "CP5": {"df_mapeo_brechas_intervenciones": df_mapeo_brechas_intervenciones,
                "df_alternativas_cp5": df_alternativas_cp5},
        "CP6": {"df_priorizacion": df_priorizacion, "df_matriz_F": df_matriz_F,
                "df_contribucion_L": df_contribucion_L},
        "CP7": {"df_operaciones": df_operaciones, "df_recursos": df_recursos,
                "df_rutas": df_rutas, "param_llegadas": param_llegadas},
        "CP8": {"df_trazabilidad_calibracion": df_trazabilidad_calibracion,
                "criterios_aceptacion": criterios_aceptacion},
        "CP9": {"df_modificaciones_tobe": df_modificaciones_tobe,
                "catalogo_escenarios": catalogo_escenarios},
        "CP10": {"df_replicas": df_replicas, "df_resumen_escenarios": df_resumen_escenarios,
                 "parametros_simulacion": parametros_simulacion},
        "CP11": {"df_evaluacion_cp11": df_evaluacion_cp11, "METAS_TOBE": METAS_TOBE}
    }

# ============================================================
# 2. VALIDACIONES
# ============================================================

def validar_dataframe(df, nombre):
    if df is None:
        return {"modulo": nombre, "estado": ESTADO_PENDIENTE_DSS, "mensaje": f"{nombre}: datos no disponibles."}
    if not isinstance(df, pd.DataFrame):
        return {"modulo": nombre, "estado": ESTADO_PENDIENTE_DSS, "mensaje": f"{nombre}: formato inválido."}
    if df.empty:
        return {"modulo": nombre, "estado": ESTADO_PENDIENTE_DSS, "mensaje": f"{nombre}: DataFrame vacío."}
    return {"modulo": nombre, "estado": ESTADO_OK, "mensaje": f"{nombre}: disponible."}

def validar_parametros_cp10(parametros):
    if parametros is None:
        return False
    requeridos = ["warm_up", "longitud_corrida", "num_replicas"]
    return all(parametros.get(x) is not None for x in requeridos)

def validar_cp10(parametros):
    if not validar_parametros_cp10(parametros):
        return {"estado": ESTADO_VALIDACION,
                "mensaje": "CP10 bloqueado: parámetros de simulación pendientes."}
    return {"estado": ESTADO_OK, "mensaje": "CP10 disponible para ejecución."}

# ============================================================
# 3. VALIDACIÓN DE ENTRADA MTO
# ============================================================

COLUMNAS_MTO_REQUERIDAS = [
    "id_orden", "fecha_ingreso", "fecha_comprometida",
    "producto_ruta", "cantidad_unidades", "estado"
]

def validar_entrada_mto(df_ordenes):
    if df_ordenes is None or df_ordenes.empty:
        return {"estado": ESTADO_PENDIENTE_DSS, "faltantes": COLUMNAS_MTO_REQUERIDAS}
    faltantes = [c for c in COLUMNAS_MTO_REQUERIDAS if c not in df_ordenes.columns]
    if faltantes:
        return {"estado": ESTADO_PENDIENTE_DSS, "faltantes": faltantes}
    return {"estado": ESTADO_OK, "faltantes": []}

def cargar_mto_desde_excel(ruta):
    df = pd.read_excel(ruta)
    v = validar_entrada_mto(df)
    if v["estado"] != ESTADO_OK:
        raise ValueError(f"Columnas faltantes: {v['faltantes']}")
    return df

def cargar_mto_desde_csv(ruta):
    df = pd.read_csv(ruta)
    v = validar_entrada_mto(df)
    if v["estado"] != ESTADO_OK:
        raise ValueError(f"Columnas faltantes: {v['faltantes']}")
    return df

# ============================================================
# 4. CONTROL DEL FLUJO CP1 → CP11
# ============================================================

def ejecutar_dss_control(datos_entrada):
    estados = []

    for modulo in ["CP1","CP2","CP3","CP4","CP5","CP6","CP7","CP8","CP9","CP10","CP11"]:
        if modulo not in datos_entrada:
            estados.append({
                "modulo": modulo,
                "estado": ESTADO_PENDIENTE_DSS,
                "mensaje": f"{modulo} no está disponible."
            })

    # CP1
    if "CP1" in datos_entrada:
        v = validar_entrada_mto((datos_entrada.get("CP1") or {}).get("df_ordenes"))
        estados.append({
            "modulo": "CP1",
            "estado": v["estado"],
            "mensaje": "Entrada MTO disponible." if v["estado"] == ESTADO_OK else "Entrada MTO pendiente."
        })

    # CP2
    if "CP2" in datos_entrada:
        for nombre in ["df_rutas_orden", "df_vsm", "df_indicadores_vsm"]:
            estados.append(validar_dataframe((datos_entrada.get("CP2") or {}).get(nombre), f"CP2/{nombre}"))

    # CP3
    if "CP3" in datos_entrada:
        estados.append(validar_dataframe((datos_entrada.get("CP3") or {}).get("df_carga_capacidad"), "CP3/df_carga_capacidad"))

    # CP4
    if "CP4" in datos_entrada:
        estados.append(validar_dataframe((datos_entrada.get("CP4") or {}).get("df_madurez_respuestas"), "CP4/df_madurez_respuestas"))

    # CP5
    if "CP5" in datos_entrada:
        for nombre in ["df_mapeo_brechas_intervenciones", "df_alternativas_cp5"]:
            estados.append(validar_dataframe((datos_entrada.get("CP5") or {}).get(nombre), f"CP5/{nombre}"))

    # CP6
    if "CP6" in datos_entrada:
        for nombre in ["df_priorizacion", "df_matriz_F", "df_contribucion_L"]:
            estados.append(validar_dataframe((datos_entrada.get("CP6") or {}).get(nombre), f"CP6/{nombre}"))

    # CP7
    if "CP7" in datos_entrada:
        for nombre in ["df_operaciones", "df_recursos", "df_rutas"]:
            estados.append(validar_dataframe((datos_entrada.get("CP7") or {}).get(nombre), f"CP7/{nombre}"))

    # CP8
    if "CP8" in datos_entrada:
        estados.append(validar_dataframe((datos_entrada.get("CP8") or {}).get("df_trazabilidad_calibracion"), "CP8/df_trazabilidad_calibracion"))

    # CP9
    if "CP9" in datos_entrada:
        for nombre in ["df_modificaciones_tobe", "catalogo_escenarios"]:
            objeto = (datos_entrada.get("CP9") or {}).get(nombre)
            if isinstance(objeto, pd.DataFrame):
                estados.append(validar_dataframe(objeto, f"CP9/{nombre}"))
            elif objeto is None:
                estados.append({"modulo": f"CP9/{nombre}", "estado": ESTADO_PENDIENTE_DSS, "mensaje": f"{nombre} no disponible."})
            else:
                estados.append({"modulo": f"CP9/{nombre}", "estado": ESTADO_OK, "mensaje": f"{nombre} disponible."})

    # CP10
    if "CP10" in datos_entrada:
        resultado_cp10 = validar_cp10((datos_entrada.get("CP10") or {}).get("parametros_simulacion"))
        estados.append({"modulo": "CP10", **resultado_cp10})

    # CP11
    if "CP11" in datos_entrada:
        estados.append(validar_dataframe((datos_entrada.get("CP11") or {}).get("df_evaluacion_cp11"), "CP11/df_evaluacion_cp11"))

    estados_df = pd.DataFrame(estados)

    if not estados_df.empty and estados_df["estado"].isin([ESTADO_PENDIENTE_DSS, ESTADO_VALIDACION]).any():
        estado_global = ESTADO_PENDIENTE_DSS
    else:
        estado_global = ESTADO_OK

    return {"estado_global": estado_global, "estados_modulos": estados_df}

# ============================================================
# 5. RESUMEN EJECUTIVO
# ============================================================

def generar_resumen_ejecutivo(
    df_indicadores_vsm=None, df_madurez=None, df_priorizacion=None,
    catalogo_escenarios=None, df_evaluacion_cp11=None
):
    resumen = {
        "estado": ESTADO_PENDIENTE_DSS,
        "diagnostico_C1": None, "madurez_C2": None,
        "priorizacion_C3": None, "escenarios": None,
        "comparacion_resultados": None, "restricciones": None,
        "decision": None
    }

    if isinstance(df_indicadores_vsm, pd.DataFrame) and not df_indicadores_vsm.empty:
        resumen["diagnostico_C1"] = df_indicadores_vsm.copy()

    if isinstance(df_madurez, pd.DataFrame) and not df_madurez.empty:
        resumen["madurez_C2"] = df_madurez.copy()

    if isinstance(df_priorizacion, pd.DataFrame) and not df_priorizacion.empty:
        resumen["priorizacion_C3"] = df_priorizacion.copy()

    if isinstance(catalogo_escenarios, pd.DataFrame) and not catalogo_escenarios.empty:
        resumen["escenarios"] = catalogo_escenarios.copy()
    elif isinstance(catalogo_escenarios, dict) and catalogo_escenarios:
        # CP9: catalogo_escenarios llega como dict {id_intervencion: escenario}.
        resumen["escenarios"] = pd.DataFrame({
            "id_intervencion": list(catalogo_escenarios.keys()),
            "escenario": list(catalogo_escenarios.values())
        })

    if isinstance(df_evaluacion_cp11, pd.DataFrame) and not df_evaluacion_cp11.empty:
        columnas_resultado = [c for c in [
            "id_escenario","intervencion",
            "LT_ASIS","LT_TOBE","WIP_ASIS","WIP_TOBE","PCE_ASIS","PCE_TOBE",
            "delta_LT_pct","delta_WIP_pct","delta_PCE_pct",
            "estado_metas","estado_restricciones","estado_final"
        ] if c in df_evaluacion_cp11.columns]
        resumen["comparacion_resultados"] = df_evaluacion_cp11[columnas_resultado]

        resumen["restricciones"] = df_evaluacion_cp11[[c for c in [
            "id_escenario","restriccion_recursos","restriccion_presupuesto",
            "restriccion_madurez","estado_restricciones"
        ] if c in df_evaluacion_cp11.columns]]

        resumen["decision"] = df_evaluacion_cp11[[c for c in [
            "id_escenario","intervencion","estado_final"
        ] if c in df_evaluacion_cp11.columns]]

        resumen["estado"] = ESTADO_OK

    return resumen

# ============================================================
# 6. TRAZABILIDAD DEL DSS
# ============================================================

COLUMNAS_TRAZABILIDAD_DSS = [
    "id_dato","id_diagnostico","id_brecha","id_intervencion","id_escenario",
    "LT_asis","WIP_asis","PCE_asis",
    "LT_tobe","WIP_tobe","PCE_tobe",
    "delta_LT_pct","delta_WIP_pct","delta_PCE_pct",
    "estado_final","fecha_estado"
]

def crear_trazabilidad_dss():
    return pd.DataFrame(columns=COLUMNAS_TRAZABILIDAD_DSS)

def construir_trazabilidad_dss(
    df_priorizacion=None, df_modificaciones_tobe=None, df_evaluacion_cp11=None
):
    df_trazabilidad_dss = crear_trazabilidad_dss()

    if not isinstance(df_evaluacion_cp11, pd.DataFrame) or df_evaluacion_cp11.empty:
        return df_trazabilidad_dss

    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _unicos(serie):
        # Valores no nulos y no vacíos, sin repetir, en orden de aparición.
        return list(dict.fromkeys(
            v for v in serie.dropna().tolist() if str(v).strip() != ""
        ))

    def _tiene(df, columnas):
        return (isinstance(df, pd.DataFrame) and not df.empty
                and all(c in df.columns for c in columnas))

    prio_ok = _tiene(df_priorizacion, ["id_intervencion", "intervencion"])
    mod_ok = _tiene(df_modificaciones_tobe, ["id_escenario", "id_intervencion"])

    for _, resultado in df_evaluacion_cp11.iterrows():
        nombre_interv = resultado.get("intervencion")
        id_escenario = resultado.get("id_escenario")

        # id_intervencion: ID real (I01, I02...). Primero se busca por nombre en
        # df_priorizacion; si no, por id_escenario en df_modificaciones_tobe.
        # Solo se acepta si el ID es único; si no se encuentra, se deja el nombre (fallback).
        id_intervencion = None
        if prio_ok and pd.notna(nombre_interv):
            ids = _unicos(df_priorizacion.loc[
                df_priorizacion["intervencion"] == nombre_interv, "id_intervencion"])
            if len(ids) == 1:
                id_intervencion = ids[0]
        if id_intervencion is None and mod_ok and pd.notna(id_escenario):
            ids = _unicos(df_modificaciones_tobe.loc[
                df_modificaciones_tobe["id_escenario"] == id_escenario, "id_intervencion"])
            if len(ids) == 1:
                id_intervencion = ids[0]
        if id_intervencion is None:
            id_intervencion = nombre_interv

        # id_brecha: brecha(s) C1 asociada(s) a la intervención en df_priorizacion["brecha_C1"].
        # Si hay más de una, se listan separadas por "; ". Si no existe, queda None.
        id_brecha = None
        if prio_ok and "brecha_C1" in df_priorizacion.columns:
            mascara = ((df_priorizacion["id_intervencion"] == id_intervencion)
                       | (df_priorizacion["intervencion"] == nombre_interv))
            brechas = _unicos(df_priorizacion.loc[mascara, "brecha_C1"])
            if brechas:
                id_brecha = "; ".join(str(b) for b in brechas)

        # id_dato e id_diagnostico: los datos actuales no traen estos identificadores
        # (dependen de una futura ampliación de CP1/CP2, por ejemplo un id_dato único
        # por orden). Quedan en None; no se inventan.
        fila = {
            "id_dato": None, "id_diagnostico": None, "id_brecha": id_brecha,
            "id_intervencion": id_intervencion,
            "id_escenario": id_escenario,
            "LT_asis": resultado.get("LT_ASIS"), "WIP_asis": resultado.get("WIP_ASIS"), "PCE_asis": resultado.get("PCE_ASIS"),
            "LT_tobe": resultado.get("LT_TOBE"), "WIP_tobe": resultado.get("WIP_TOBE"), "PCE_tobe": resultado.get("PCE_TOBE"),
            "delta_LT_pct": resultado.get("delta_LT_pct"),
            "delta_WIP_pct": resultado.get("delta_WIP_pct"),
            "delta_PCE_pct": resultado.get("delta_PCE_pct"),
            "estado_final": resultado.get("estado_final"),
            "fecha_estado": fecha_actual
        }
        df_trazabilidad_dss = pd.concat([df_trazabilidad_dss, pd.DataFrame([fila])], ignore_index=True)

    return df_trazabilidad_dss

# ============================================================
# 7. FUNCIÓN MAESTRA ejecutar_dss()
# ============================================================

def ejecutar_dss(datos_entrada):
    control = ejecutar_dss_control(datos_entrada)

    resumen = generar_resumen_ejecutivo(
        df_indicadores_vsm=(datos_entrada.get("CP2") or {}).get("df_indicadores_vsm"),
        df_madurez=(datos_entrada.get("CP4") or {}).get("df_madurez_respuestas"),
        df_priorizacion=(datos_entrada.get("CP6") or {}).get("df_priorizacion"),
        catalogo_escenarios=(datos_entrada.get("CP9") or {}).get("catalogo_escenarios"),
        df_evaluacion_cp11=(datos_entrada.get("CP11") or {}).get("df_evaluacion_cp11")
    )

    df_trazabilidad_dss = construir_trazabilidad_dss(
        df_priorizacion=(datos_entrada.get("CP6") or {}).get("df_priorizacion"),
        df_modificaciones_tobe=(datos_entrada.get("CP9") or {}).get("df_modificaciones_tobe"),
        df_evaluacion_cp11=(datos_entrada.get("CP11") or {}).get("df_evaluacion_cp11")
    )

    estado_global = control["estado_global"]

    if estado_global != ESTADO_OK:
        decision_global = "PENDIENTE_DATOS: no existe evidencia suficiente para emitir una recomendación definitiva."
    else:
        decision_global = "Evaluación disponible según los resultados de los módulos integrados."

    return {
        "estado_global": estado_global,
        "control_flujo": control["estados_modulos"],
        "resumen_ejecutivo": resumen,
        "df_trazabilidad_dss": df_trazabilidad_dss,
        "decision_global": decision_global
    }

# ============================================================
# 8. PRUEBA DE HUMO (DESACTIVADA) — DSS con datos vacíos
# ============================================================
#
# print("=== CP12: INTEGRACIÓN DEL DSS ===\n")
#
# # Entrada de prueba (DataFrames vacíos, valores None)
# datos_prueba = crear_entrada_dss(
#     df_ordenes=pd.DataFrame(columns=COLUMNAS_MTO_REQUERIDAS),
#     df_indicadores_vsm=df_indicadores_vsm if 'df_indicadores_vsm' in globals() else None,
#     df_madurez_respuestas=df_madurez_respuestas if 'df_madurez_respuestas' in globals() else None,
#     df_priorizacion=pd.DataFrame(),
#     catalogo_escenarios=pd.DataFrame(),
#     df_evaluacion_cp11=pd.DataFrame(),
#     parametros_simulacion={"warm_up": None, "longitud_corrida": None, "num_replicas": None}
# )
#
# print("Ejecutando DSS con datos vacíos...\n")
#
# resultado = ejecutar_dss(datos_prueba)
#
# print(f"Estado global: {resultado['estado_global']}")
# print(f"\nDecisión global: {resultado['decision_global']}")
#
# print("\nControl de flujo por módulo:")
# print(resultado["control_flujo"])
#
# print("\nEstructura del resumen ejecutivo:")
# for k in resultado["resumen_ejecutivo"].keys():
#     print(f"  - {k}")
#
# print("\nEstructura de trazabilidad:")
# print(f"  Columnas: {resultado['df_trazabilidad_dss'].columns.tolist()}")
# print(f"  Filas: {len(resultado['df_trazabilidad_dss'])}")
#
# print("\nCP12: DSS integrado preparado correctamente.")
# print("NOTA: El sistema reporta PENDIENTE_DATOS porque faltan datos reales.")
# print("      Esto es correcto: no emite recomendaciones sin evidencia.")

__version__ = "1.1.0"
