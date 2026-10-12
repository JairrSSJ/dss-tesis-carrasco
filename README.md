# DSS de Lead Time — Industrias Marcelo S.A.C.

Interfaz en Streamlit del DSS (Decision Support System) de la tesis de Ingeniería Industrial
**«Framework basado en VSM Digital y evaluación de madurez digital para optimizar el Lead Time
en una industria metalmecánica MTO»**.

El flujo del framework es: **C1 VSM Digital → C2 Madurez Digital → C3 Priorización Lean 4.0**,
validado por Simulación de Eventos Discretos (DES) y evaluado en el CP11.

- Caso: Industrias Marcelo S.A.C. (PyME metalmecánica peruana, equipos gastronómicos de acero
  inoxidable, modalidad Make-to-Order).
- Usuario objetivo: supervisor de planta, sin conocimientos de programación.
- Regla del proyecto: la interfaz **no inventa datos ni parámetros**. Lo que falta se reporta como
  `PENDIENTE_DATOS`.

## Estructura del repositorio

```text
.
├── app.py                  # Interfaz Streamlit (9 módulos)
├── dss_core.py             # Motor del DSS: debe definir ejecutar_dss(datos_entrada)
├── requirements.txt
├── README.md
└── .streamlit/
    └── config.toml         # Tema visual

`dss_core.py` contiene el código de los checkpoints CP1 a CP12 consolidado en un solo módulo, con la
función maestra `ejecutar_dss(datos_entrada)`. Si el motor usa alguna librería adicional a las de
`requirements.txt`, debe agregarse allí (`PENDIENTE_DATOS`: confirmar con el entorno de Colab).

## Módulos de la interfaz

1. Inicio (carga de datos)
2. C1 VSM Digital
3. C2 Madurez Digital
4. C3 Priorización Lean 4.0
5. Escenarios TO-BE
6. DES (simulación): muestra el control de flujo, es decir, el estado de cada módulo del DSS
7. Evaluación CP11
8. Trazabilidad DSS
9. Reporte final

## Despliegue en Streamlit Cloud

1. Cree un repositorio en GitHub con los archivos de la sección «Estructura del repositorio».
2. Entre a Streamlit Community Cloud e inicie sesión con GitHub.
3. Pulse **New app** y seleccione el repositorio, la rama y el archivo principal `app.py`.
4. Pulse **Deploy**. Streamlit instalará las librerías de `requirements.txt`.
5. Registre las direcciones obtenidas:
   - URL del repositorio: `https://github.com/JairrSSJ/dss-tesis-carrasco`
   - URL de la app desplegada: `https://dss-tesis-carrasco-dtkakh58fjpufmiyuwh7o2.streamlit.app`

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
## Formato de los archivos de entrada

- **Excel (.xlsx):** una hoja por tabla. **CSV (.csv):** un archivo por tabla, con el mismo nombre que
  tendría la hoja.
- El nombre de cada hoja es `CPn_nombre_de_la_tabla`. Por ejemplo, la hoja `CP1_df_ordenes` se carga
  como la tabla `df_ordenes` del CP1.
- Excel limita los nombres de hoja a 31 caracteres. Por eso la tabla
  `df_mapeo_brechas_intervenciones` del CP5 se carga desde una hoja llamada `CP5_df_mapeo_brechas`
  (alias definido en `HOJAS_ALIAS` dentro de `app.py`). En CSV puede usarse cualquiera de los dos nombres.
- Los diccionarios de parámetros (CP7 a CP11) van en **una hoja con las columnas `clave`, `valor` y
  `grupo`**. El grupo indica el destino con el formato `CPn.nombre_del_diccionario`. En `valor` puede
  ir un número, un texto o un JSON (por ejemplo `{"a": 1}`).
- Las celdas vacías o marcadas como `PENDIENTE_DATOS` se reportan en la interfaz; no se completan.
- Las hojas cuyo nombre no sigue la convención se ignoran y se avisa en pantalla.

## Estructura esperada de los datos de entrada

La interfaz arma el diccionario `datos_entrada` que recibe `ejecutar_dss`:

| Checkpoint | Tablas (hojas `CPn_<tabla>`) | Diccionarios (hoja `clave`/`valor`/`grupo`) |
|---|---|---|
| CP1 | `df_ordenes`, `df_procesos`, `df_recursos`, `df_madurez`, `df_simulacion` | — |
| CP2 | `df_rutas_orden`, `df_vsm`, `df_indicadores_vsm` | — |
| CP3 | `df_carga_capacidad` | — |
| CP4 | `df_madurez_respuestas` | — |
| CP5 | `df_mapeo_brechas_intervenciones`, `df_alternativas_cp5` | — |
| CP6 | `df_priorizacion`, `df_matriz_F`, `df_contribucion_L` | — |
| CP7 | `df_operaciones`, `df_recursos`, `df_rutas` | `CP7.param_llegadas` |
| CP8 | `df_trazabilidad_calibracion` | `CP8.criterios_aceptacion` |
| CP9 | `df_modificaciones_tobe` | `CP9.catalogo_escenarios` |
| CP10 | `df_replicas`, `df_resumen_escenarios` | `CP10.parametros_simulacion` |
| CP11 | `df_evaluacion_cp11` | `CP11.METAS_TOBE` |

Equivale a:

```python
datos_entrada = {
    "CP1": {"df_ordenes": ..., "df_procesos": ..., "df_recursos": ..., "df_madurez": ..., "df_simulacion": ...},
    "CP2": {"df_rutas_orden": ..., "df_vsm": ..., "df_indicadores_vsm": ...},
    "CP3": {"df_carga_capacidad": ...},
    "CP4": {"df_madurez_respuestas": ...},
    "CP5": {"df_mapeo_brechas_intervenciones": ..., "df_alternativas_cp5": ...},
    "CP6": {"df_priorizacion": ..., "df_matriz_F": ..., "df_contribucion_L": ...},
    "CP7": {"df_operaciones": ..., "df_recursos": ..., "df_rutas": ..., "param_llegadas": {...}},
    "CP8": {"df_trazabilidad_calibracion": ..., "criterios_aceptacion": {...}},
    "CP9": {"df_modificaciones_tobe": ..., "catalogo_escenarios": {...}},
    "CP10": {"df_replicas": ..., "df_resumen_escenarios": ..., "parametros_simulacion": {...}},
    "CP11": {"df_evaluacion_cp11": ..., "METAS_TOBE": {...}},
}

### `decision_global`

- Si falta, está vacío o contiene `PENDIENTE_DATOS`: aviso naranja. No se formula ninguna
  recomendación desde la interfaz.
- Si es texto real: cuadro verde con el texto del DSS.

### `df_trazabilidad_dss`

Columnas: `id_dato`, `id_diagnostico`, `id_brecha`, `id_intervencion`, `id_escenario`, `LT_asis`,
`WIP_asis`, `PCE_asis`, `LT_tobe`, `WIP_tobe`, `PCE_tobe`, `delta_LT_pct`, `delta_WIP_pct`,
`delta_PCE_pct`, `estado_final`, `fecha_estado`.

Se muestra en el módulo **Trazabilidad DSS** y se descarga en CSV (codificación `utf-8-sig`, para que
Excel abra bien las tildes). Si el DSS no la devuelve, la interfaz lo avisa y no genera ninguna tabla.

## Línea base declarada del caso

| Indicador | Valor |
|---|---|
| Lead Time promedio | 24,5 días |
| WIP | 18 unidades |
| PCE | 8,5 % |
| Pedidos fuera de fecha | 42 % |

En el Reporte final, la interfaz lee del diagnóstico C1 los indicadores `Lead Time promedio`,
`WIP Plegado-Soldadura`, `PCE` y `Pedidos fuera de fecha` y los compara con esta línea base.
Si el DSS no los entrega, se muestran como `PENDIENTE_DATOS` con el motivo.

## Trazabilidad

Cada ejecución queda registrada en la sesión con la huella SHA-256 de la entrada, los archivos
cargados, la versión y la huella del código del DSS, y la salida completa. La cadena
**dato → diagnóstico → intervención → escenario → resultado** se documenta en el módulo
**Trazabilidad DSS** y se exporta en `.json`.

## Pendientes

| Elemento | Estado |
|---|---|
| URL del repositorio | `https://github.com/JairrSSJ/dss-tesis-carrasco` |
| URL de la app desplegada | `https://dss-tesis-carrasco-dtkakh58fjpufmiyuwh7o2.streamlit.app` |
| Versiones fijas de librerías | No se fijan; se usan las últimas estables |
| Librerías adicionales requeridas por `dss_core.py` | `PENDIENTE_DATOS` (confirmar contra Colab) |
