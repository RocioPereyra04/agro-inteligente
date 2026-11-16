# AgroRota ML v2 — índices satelitales, clima, riego y rotación

Esta versión cambia el objetivo del modelo anterior. El Random Forest **se entrena con la serie real de NDVI, MSI, precipitación y temperatura** de la parcela. No aprende a reproducir una rúbrica sintética.

**Importante sobre el artefacto:** este paquete entrega el código de entrenamiento y predicción, pero no incluye un `.joblib` entrenado con tus datos reales, porque `dataset_agricola.csv` y `weather_parcela.csv` no fueron adjuntados a esta conversación. El `.joblib` se crea en tu computadora al ejecutar `train_model.py`. No uses el modelo sintético del paquete de demostración anterior para esta versión.

## 1. Qué aprende el Random Forest

El modelo es un `RandomForestRegressor` multisalida. Para cada observación Sentinel válida en la fecha `t`, usa:

- NDVI y MSI medios observados en `t`;
- dispersión y cantidad de píxeles válidos;
- cambio diario de NDVI/MSI respecto de la observación válida anterior;
- precipitación acumulada de 7 y 30 días;
- temperatura media, máxima y mínima de las ventanas 7/30 días;
- estacionalidad (seno/coseno del día del año).

Y aprende a predecir los **NDVI y MSI medidos en la siguiente observación Sentinel válida**, si ocurre dentro de 60 días. Los objetivos son valores reales del dataset, no etiquetas fabricadas.

Esto sirve para una demo de pronóstico de la señal satelital de la parcela. **No es un clasificador de cultivos:** como el polígono es fijo y el dataset contiene promedios de toda la parcela, el modelo no sabe qué especie genera cada píxel. Si dentro del polígono hay varias especies o sectores, la salida es un estado promedio de la parcela, no un diagnóstico por cultivo. No predice especie, floración, cosecha, rendimiento ni consumo de agua medido.

### Validación

La división es cronológica por fecha objetivo: 70 % inicial para entrenamiento, 15 % para validación y 15 % final para test. No se mezclan aleatoriamente fechas futuras con pasadas. En test se comparan Random Forest y una línea base de persistencia (el último NDVI/MSI se mantiene). Si el RF no supera la persistencia, debe mostrarse como pronóstico experimental de baja habilidad.

Se guarda MAE, RMSE y R² de NDVI y MSI, además de MAE de persistencia.

## 2. Datos necesarios

El proyecto espera que ya hayas ejecutado `basededatos.py` y que existan:

```text
agro_inteligente/
├── data/processed/
│   ├── dataset_agricola.csv       # 522 fechas Sentinel + NASA POWER integrado
│   └── weather_parcela.csv       # serie diaria NASA POWER
└── agrorota_ml_v2/
```

El integrado debe incluir `fecha`, `NDVI_mean`, `MSI_mean`, ventanas de precipitación y temperatura de 7/30 días. Se reconocen los nombres creados por el `preprocessing.py` del proyecto.

No se rellenan NDVI/MSI faltantes con cero. Para el entrenamiento se descartan valores sin índice y observaciones con menos del 60 % del máximo de píxeles válidos (la parcela tenía un máximo de 22 píxeles en el EDA). Si la calidad cambia, revisar `MIN_VALID_PIXEL_FRACTION` en `config.py`.

## 3. Cultivos considerados

Se incluyen únicamente los siete solicitados:

1. Lechuga — Asteraceae.
2. Zapallo coreano — se asocia provisionalmente al registro general `Cucurbita maxima / C. moschata`; confirmar variedad.
3. Frutilla — Rosaceae.
4. Naranja/cítricos — Rutaceae.
5. Melón — Cucurbitaceae.
6. Sandía — Cucurbitaceae.
7. Ciruelo — **el CSV lo identifica como `Spondias purpurea` (ciruela tropical/jocote), familia Anacardiaceae**. Confirmar especie local antes de usar esa familia.

El catálogo también muestra Tomate en naranja, pero no está entre los siete que pediste en el último mensaje; por eso quedó fuera de esta primera versión. Si debe incluirse, añadirlo explícitamente al catálogo seleccionado.

Las fichas del catálogo son requisitos/recomendaciones generales de cada cultivo. No describen el suelo medido de la parcela. El escenario local se conserva como dos alternativas (`arenoso` y `franco-limoso`) hasta confirmar la textura.

## 4. Estado del cultivo: qué se puede y no se puede inferir

Se separan dos salidas:

- **Estado espectral:** cobertura muy baja, vegetación escasa, moderada, densa o posible estrés. Se obtiene del NDVI/MSI reciente, sus tendencias y la referencia histórica de la propia parcela.
- **Fase de calendario:** siembra directa, almácigo, trasplante, cultivo o ventana de cosecha, tomada del plano mensual.

El plano no contiene una fase de floración. NDVI/MSI a 20 m y promediados sobre toda la parcela no permiten confirmar floración ni cosecha. Tampoco permiten afirmar “marchito”; se puede mostrar “posible estrés/caída de vigor” y pedir comprobación en campo. “NDVI bajo” significa señal de vegetación baja/suelo posiblemente expuesto, no prueba de que no haya cultivo.

**Importante:** la serie satelital actual es un promedio de la parcela fija. Si en ese mismo polígono hay varios cultivos simultáneos en sectores distintos, hay que crear polígonos de unidades de manejo; de lo contrario NDVI/MSI mezclan las coberturas y no se puede atribuir el estado a lechuga, frutilla, naranja, etc.

## 5. Riego semanal en mm

La rutina calcula una estimación orientativa:

1. Estima ETo diaria con Hargreaves-Samani usando Tmedia, Tmax, Tmin y latitud del centroide.
2. Calcula ETc = ETo × Kc.
3. Resta una aproximación simple de lluvia efectiva.
4. Distribuye el total semanal neto en pulsos ilustrativos: cuatro para escenario arenoso y tres para franco-limoso.

Para lechuga, melón, sandía, zapallo tipo invierno y frutilla se incluyen coeficientes Kc de referencia FAO-56. Para cítricos se informa rango porque varía con cobertura de copa y cubierta del suelo. Para `Spondias purpurea` no se inventa un Kc: el módulo no calcula mm de ese cultivo hasta definir un coeficiente apropiado.

El Kc varía con la etapa del cultivo; el plano mensual aproxima etapas, pero no contiene fecha real de implantación. Puede pasarse `--fase-riego inicio|medio|final` para ajustar el supuesto.

### Pronóstico de siete días

- Si existe `data/processed/weather_forecast.csv` con los próximos siete días, el módulo lo usa.
- Si no existe, crea una **climatología de referencia** con los diez años de NASA POWER (días del año ±15). Eso NO es un pronóstico meteorológico para la semana actual.

Se usa precipitación efectiva simplificada como supuesto de demo. Los mm son netos estimados, no una orden de riego ni una dosis exacta. Para convertir: 1 mm = 1 L/m² = 10 m³/ha.

El plan no conoce capacidad de campo, punto de marchitez, profundidad efectiva, eficiencia del sistema, caudal ni humedad real del perfil. Por eso las frecuencias 4/3 son escenarios de distribución, no reglas universales. Ajustar con medición de suelo y sistema de riego.

### Latitud de la parcela

La geometría sigue siendo la que ya está fija en `basededatos.py`; no se cambia. Para Hargreaves hace falta su latitud. En el código donde ya tenés la variable `parcela` de Earth Engine, podés obtenerla así:

```python
centroide = parcela.centroid(maxError=1).coordinates().getInfo()
longitud_centroide, latitud_centroide = centroide
print("Centroide (lon, lat):", longitud_centroide, latitud_centroide)
```

Luego pasar `--latitud` con ese valor, sin modificar el polígono.

## 6. Materia orgánica y nutrientes

Con NDVI, MSI, precipitación y temperatura **no se puede diagnosticar materia orgánica baja** ni decidir una dosis de N, P o K. Un NDVI bajo también puede deberse a suelo desnudo, etapa del cultivo, agua, salinidad, enfermedad, sombra o máscara de nubes.

La salida de la demo deja MO y nutrientes como “no medidos / no inferibles” y pide análisis de suelo (MO o carbono orgánico, N, P, K, pH y conductividad eléctrica) antes de recomendar fertilización. NASA POWER puede proporcionar indicadores regionales de humedad del suelo mediante SMAP (~9 km), pero eso representa agua en el suelo, no materia orgánica, y es mucho más grueso que una parcela pequeña.

## 7. Instalación y ejecución en Windows

Ubicá `agrorota_ml_v2` dentro de `agro_inteligente`, al mismo nivel que `data`.

```powershell
cd S:\Escritorio\Designdigital\CURSO_FPGA\TP2\agro_inteligente\agrorota_ml_v2
& S:\Anaconda\envs\envPruebaFPGA\python.exe -m pip install -r requirements.txt
```

### Comprobar la base antes de entrenar

```powershell
& S:\Anaconda\envs\envPruebaFPGA\python.exe check_data.py
```

El diagnóstico informa cuántas fechas conservan NDVI/MSI, cuántas superan el filtro de píxeles y cuántos pares temporales se pueden usar.

### Entrenar usando los datos reales integrados

```powershell
& S:\Anaconda\envs\envPruebaFPGA\python.exe train_model.py
```

Esto genera:

```text
models/rf_predice_indices.joblib
reports/metricas_test.csv
reports/metricas_modelo.json
reports/predicciones_test_temporal.csv
reports/resumen_entrenamiento.json
```

### Cargar modelo y realizar inferencia

Ejemplo con melón:

```powershell
& S:\Anaconda\envs\envPruebaFPGA\python.exe predict.py --cultivo-actual "Melón" --latitud -33.0
```

Reemplazá `-33.0` por la latitud real del centroide de tu polígono. Ejemplos de otros cultivos:

```powershell
& S:\Anaconda\envs\envPruebaFPGA\python.exe predict.py --cultivo-actual "Lechuga" --latitud LATITUD_REAL
& S:\Anaconda\envs\envPruebaFPGA\python.exe predict.py --cultivo-actual "Zapallo" --latitud LATITUD_REAL
& S:\Anaconda\envs\envPruebaFPGA\python.exe predict.py --cultivo-actual "Naranja" --latitud LATITUD_REAL
& S:\Anaconda\envs\envPruebaFPGA\python.exe predict.py --cultivo-actual "Frutilla" --latitud LATITUD_REAL
```

Para proporcionar un pronóstico real, guardá `weather_forecast.csv` con siete filas y estas columnas:

```text
fecha,precipitacion_mm_dia,temperatura_media_c,temperatura_maxima_c,temperatura_minima_c
```

Hay una plantilla de ejemplo en `inputs/weather_forecast_template.csv`; sus números son ilustrativos y no deben usarse como pronóstico real.

## 8. Archivos de salida de inferencia

- `estado_parcela_actual.csv/json`: fecha de consulta, fecha de última imagen válida, índices, predicción de siguiente observación, estado espectral, tendencia (crecimiento/estable/descenso), fase mensual del plano y advertencias.
- `comparacion_rotaciones.csv`: dos escenarios de suelo y puntaje fijo 50 % agua / 50 % proxy de cuidado del suelo, con filtros de familia y temperatura.
- `plan_riego_7_dias.csv`: ETo, ETc estimada, precipitación, déficit y distribución orientativa de mm por día.

El puntaje de cuidado del suelo es un proxy transparente construido con textura de catálogo, profundidad radicular y demanda nutricional; no es una medición de aumento de materia orgánica. Las fichas con requisito de MO quedan marcadas para análisis.

Para un cultivo actual perenne (naranja o `Spondias purpurea`), el programa no propone reemplazar el árbol por una hortaliza anual. Muestra como opciones complementarias mantener el arbolado con cobertura viva o con acolchado, sin asignarles puntaje numérico porque no son cultivos del catálogo ni se conoce la especie de cobertura.

## 9. Fuentes metodológicas y resolución

- FAO-56 define el método de coeficiente de cultivo como `ETc = Kc × ETo`; Kc cambia con el cultivo y su etapa. El cálculo de esta demo usa Hargreaves-Samani como aproximación porque la serie disponible contiene temperaturas, pero no todas las variables necesarias para Penman-Monteith. La FAO presenta Hargreaves como alternativa y recomienda verificar/calibrar localmente: https://www.fao.org/4/X0490E/x0490e07.htm
- Referencia de Kc por grupo y etapa: FAO-56, Tabla 12: https://www.fao.org/4/X0490E/x0490e0b.htm. Los valores de zapallo se aproximan a `pumpkin/winter squash`; verificar variedad y condiciones.
- NASA POWER indica que los datos meteorológicos base tienen resolución aproximada de 0,5° × 0,625°; los productos de precipitación IMERG (~10 km) y humedad SMAP (~9 km) son productos de mayor resolución disponibles por rutas específicas: https://power.larc.nasa.gov/docs/methodology/ y https://power.larc.nasa.gov/docs/methodology/data/sources_hydrology/. Aun así, son más gruesos que una pequeña parcela.

## 10. Qué se debe considerar para la presentación

- El RF sí se entrena con observaciones reales de NDVI/MSI futuras y predictores NASA POWER.
- El test es temporal y se compara contra persistencia; aún es una validación de una sola parcela.
- El riego y la rotación son módulos híbridos de cálculo/reglas; no se presentan como salidas aprendidas del RF.
- No se predicen floración, cosecha exacta, materia orgánica, nutrientes ni rendimiento con la información actual.
- Para un segundo modelo por cultivo/sector se necesitan polígonos de unidades de manejo o etiquetas de cultivo vinculadas a fechas.

## 11. Alertas diferenciales de suelo, nutrición y sanidad (nuevo)

La inferencia también genera:

```text
reports/alertas_suelo_nutricion_sanidad.csv
reports/diagnostico_agronomico.json
```

Estas alertas son un **cribado para priorizar recorridas y mediciones**, no diagnósticos automáticos. El módulo `src/diagnostics.py` utiliza percentiles históricos de la propia parcela (por ejemplo, Q20/Q75 de NDVI/MSI y Q50/Q95 de lluvia de 7 días) y combina tendencias recientes. Los percentiles son referencias internas para la demo, no límites fisiológicos universales.

| Alerta | Regla exploratoria | Qué permite decir | Qué NO permite afirmar |
|---|---|---|---|
| Posible restricción física | Patrón repetido de NDVI descendente + MSI ascendente con lluvia 7d no baja | Revisar raíces, perfil, drenaje y resistencia del suelo | No confirma compactación, tosca ni capa arcillosa |
| Bajo vigor no explicado claramente por lluvia | NDVI bajo relativo a la época, MSI no elevado y precipitación no baja | Revisar nutrición, pH, salinidad, raíces y etapa del cultivo | No identifica N, P, K ni recomienda fertilizante |
| Riesgo potencial de lixiviación | Precipitación 7d en Q95 histórico y escenario arenoso | Si hubo N disponible, revisar posible movimiento por el perfil | No demuestra nitrato perdido ni cuantifica lixiviación |
| Vigilancia sanitaria climática | Lluvia 7d alta relativa y temperatura media en banda amplia de vigilancia | Intensificar monitoreo de hojas, frutos, cuello y raíces | No predice infección ni identifica un patógeno |
| Estrés con lluvia regional | NDVI baja y MSI sube aun cuando la lluvia 7d no es baja | Investigar causas no explicadas por sequía regional | No distingue enfermedad, nematodos, compactación, salinidad o anegamiento |

### Verificación recomendada por alerta

- **Compactación/tosca:** abrir calicatas, observar profundidad y forma de las raíces y medir resistencia con penetrómetro con el perfil cerca de capacidad de campo. Comparar zonas afectadas y de referencia. La humedad del suelo cambia mucho la lectura del penetrómetro.
- **Nutrición:** analizar suelo por zona (MO/carbono orgánico, pH, CE, N disponible, P y K) y, cuando aplique, complementar con análisis foliar. NDVI/MSI son señales indirectas, no mediciones químicas.
- **Lixiviación:** registrar fecha/dosis de fertilización; medir nitrato residual por profundidad o nitrato del agua de drenaje. La lluvia y una caída de NDVI por sí solas no demuestran lixiviación.
- **Plagas/enfermedades:** inspeccionar plantas y raíces y registrar síntomas, cultivo, variedad y etapa. Para modelos epidemiológicos específicos faltan humedad relativa y horas de mojado foliar, preferentemente datos horarios, además de un patógeno objetivo.

### Limitación espacial

La tabla `dataset_agricola.csv` contiene estadísticas agregadas de todo el polígono. Por tanto, las alertas se refieren a la parcela completa y **no pueden señalar “manchones” ni coordenadas**. Para localizarlos se debe conservar/exportar NDVI y MSI raster por fecha y procesar unidades de manejo o ventanas/polígonos internos. La banda B11 de Sentinel-2 es de 20 m; las estadísticas actuales alcanzaban como máximo unos 22 píxeles por parcela, por lo que la resolución intralote sigue siendo limitada.

### Limitaciones meteorológicas

NASA POWER meteorológico usa una grilla regional (aprox. 0,5° × 0,625° en la documentación actual). La lluvia de POWER no confirma que haya llovido igual en cada sector del predio. El módulo no utiliza humedad relativa ni mojado foliar, por lo que “vigilancia sanitaria” no es un pronóstico fitopatológico.

**Acción en la interfaz:** mostrar el nombre de la alerta, la evidencia que la activó, la hipótesis que conviene revisar y un botón/acción “Marcar como inspeccionado”. No mostrar “compactado”, “falta nitrógeno”, “nitrato lavado” o nombres de enfermedades como diagnóstico confirmado.
