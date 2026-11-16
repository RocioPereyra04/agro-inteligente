# AgroRota ML v2.1 — módulo de alertas diferenciales

Se agrega `src/diagnostics.py` y se integra a `src/inference.py`.

Nuevas salidas:
- `reports/alertas_suelo_nutricion_sanidad.csv`
- `reports/diagnostico_agronomico.json`

Alertas exploratorias:
- `ESTRES_CON_LLUVIA`
- `POSIBLE_RESTRICCION_FISICA`
- `BAJO_VIGOR_NO_EXPLICADO_POR_SEQUIA`
- `RIESGO_POTENCIAL_LIXIVIACION`
- `VIGILANCIA_SANITARIA_CLIMATICA`

El módulo no diagnostica causas. Usa tendencias y percentiles históricos internos para recomendar verificaciones de campo. No localiza manchas dentro de la parcela porque el dataset actual contiene estadísticas agregadas del polígono.

Pruebas ejecutadas: `python -m py_compile ...` y `python test_diagnostics.py`. Se probaron series sintéticas normal, estrés combinado, bajo vigor y lluvia extrema. No se ejecutó sobre el dataset real de la parcela porque sus CSV no están disponibles en este entorno.
