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