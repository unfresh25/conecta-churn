# Diseño — Prueba técnica Conecta+ (Científico de Datos Senior)

Fecha: 2026-11-20 · Estado: borrador para aprobación

## 1. Intención

Resolver la prueba técnica de NTT Data para el nivel **Senior** (partes 1 a 6 obligatorias):

1. **¿A quién contactar en los próximos 90 días?** Una probabilidad de churn por cada cliente activo al 31-dic-2025 y una decisión de contacto que maximice el valor en pesos.
2. **¿Por qué se están yendo?** Hallazgos para la gerencia, con evidencia y acciones.

La evaluación pesa sobre todo en la **sustentación en vivo**: el candidato defiende cada decisión, hace un cambio de requisito en vivo y explica qué le haría desconfiar de sus resultados. Lo califican contra la realidad (`predicciones.csv`) y por su criterio.

**Reparto de trabajo** (actualizado el 2026-11-20): Claude propone el enfoque y el candidato decide. **Claude escribe el código**: el notebook, los módulos `.py`, las pruebas y el dashboard. El candidato revisa cada parte, la adapta o pide correcciones, y tiene que poder defenderla en vivo. Por eso el trabajo avanza con pausas de revisión. Esta división se declara tal cual en `BITACORA_IA.md`.

## 2. Objetivos, no-objetivos y anti-objetivos

**Objetivos**
- Un modelo de churn a 90 días bien calibrado, validado por tiempo y comparable contra una base simple.
- Una regla de contacto basada en valor esperado por cliente, con el valor estimado de la campaña.
- Integrar tickets (texto) y logs de uso como variables, y medir cuánto aportan.
- Un hallazgo principal y dos de apoyo, con evidencia y acción.
- Media página de producción.
- MLflow con 4 corridas y tabla comparativa.
- Entregables: `README.md`, `solucion.ipynb` (con botón "Open in Colab"), `requirements.txt`, `predicciones.csv`, `MEMO.md`, `BITACORA_IA.md`.

**No-objetivos**
- Muchas familias de modelos o búsquedas grandes de hiperparámetros.
- Corregir el efecto de los llamados de retención dentro del modelo (se analiza aparte, ver §6.6).
- Un agente conversacional o una app en Next.js (se descartaron por ahora).

**Anti-objetivos** (cosas que harían fracasar el trabajo aunque "funcione")
- Fugas de información: usar `estado_actual`, contactos de retención posteriores al corte o facturas cargadas después del corte.
- Una validación inflada por cortes traslapados sin separación.
- Elegir el modelo por AUC en lugar de por valor en pesos.
- Un notebook que no corra de principio a fin en Colab, o que dependa de API keys.
- Subir los datos al repositorio.

## 3. Restricciones

- Fecha "hoy" en los datos: **31-dic-2025**. Plazo: 2 días calendario, ~6 a 10 horas.
- Todo gratuito y ejecutable en **Google Colab**. Nada de ejecutables ni scripts fuera de Colab. Se permiten módulos `.py`.
- El notebook espera `datos_conecta.zip` subido a Colab o leído desde Drive, como en `inicio.ipynb`.
- Sin API keys en el repo.
- Supuestos económicos: contacto = 25.000 COP. La oferta retiene al 40 % de quienes iban a cancelar. Valor de retener = 12 × mensualidad actual. Contactar a quien no iba a cancelar pierde el costo del contacto. Precios: Básico 23.900, Estándar 34.900, Premium 49.900, Familiar 59.900.
- `predicciones.csv`: una fila por cada cliente de `clientes_a_puntuar` (1.556), con las columnas `cliente_id` (entero), `probabilidad` (0 a 1) y `contactar` (0 o 1).

## 4. Lo que hay en los datos (recon ya hecha)

**Fuentes:** `conecta.db` (SQLite: `clientes` 3.000, `suscripciones` 3.361, `facturas` 34.138, `etiquetas_entrenamiento` 4.693, `clientes_a_puntuar` 1.556), `tickets.jsonl` (4.452) y `eventos.jsonl.gz` (103.927, solo 2025).

**Problemas encontrados y cómo se tratan**

| Problema | Tratamiento |
|---|---|
| `ciudad`: 17 grafías para 6 ciudades (BOGOTA, bogota d.c., B/quilla, Santiago de Cali…) | Normalizar a 6 valores: Bogotá, Medellín, Cali, Barranquilla, Bucaramanga, Pereira |
| `edad` con 0 (31) y 999 (34) | Pasar a nulo y agregar un indicador de "edad inválida" |
| `estado_actual` = estado de hoy y no del corte (0 churn entre los "activo") | **Excluir**: es fuga |
| `contactado_por_retencion` / `fecha_contacto_retencion`: 90 % de los contactos de entrenamiento ocurrió después del corte | Usar solo contactos con fecha ≤ corte, o excluir. Decisión del builder (§9) |
| Facturas duplicadas por (cliente, periodo, suscripción): 1.376 casos. 677 tienen el mismo `factura_id` (recarga del sistema); el resto tiene id distinto (cobro doble real) | Quitar las recargas. Conservar los cobros dobles reales como variable ("cobros duplicados") |
| `fecha_carga` de facturas: 1 a 4 días después del inicio del periodo | Filtrar facturas por `fecha_carga` ≤ corte, no por periodo |
| `fecha_pago` nula (1.474), concentrada en 2025-12 | No pagada a la fecha. Variable de mora calculada a la fecha del corte |
| Básico pasó de 19.900 a 23.900 en abr-2025 | Contexto para el hallazgo y para las variables de precio |
| `motivo_cancelacion = cambio_plan`: no es churn, porque se abre otra suscripción | La reconstrucción de etiquetas ya lo maneja (§6.1) |
| Tickets en **dos esquemas**. A (2023–2025): `ticket_id, customer: "CL-012375", created_at (UTC), category, text, status, csat`. B (2025): `id, cliente: {id, segmento}, fecha (-05:00), tipo: {principal, sub}, mensajes: [{autor, texto}], estado: {valor, fecha}, satisfaccion: {csat}` | Unificar en un esquema. `cliente_id` entero. Fechas a hora de Colombia. Texto = primer mensaje del cliente. Los mensajes del agente (3 frases fijas) se descartan |
| Tickets: 38 textos únicos de cliente, ~1/3 sarcásticos | Ver §6.4 |
| Eventos: `event_id` duplicados (1.616) | Deduplicar |

## 5. Enfoques considerados

### 5.1 Datos de entrenamiento (decidido: B sobre 2025)

- **A. Solo las 3 etiquetas entregadas** (4.693 filas, 652 churn). Es simple, pero tiene pocos positivos y un solo corte de validación.
- **B. Cortes mensuales reconstruidos desde `suscripciones` ← elegido, restringido a 2025.** La regla de churn (activo en el corte y sin suscripción activa a los 90 días) reproduce las 4.693 etiquetas entregadas con **100 % de coincidencia**. Los cortes de fin de mes de ene a sep de 2025 dan **13.600 filas y 1.815 churn**. Se restringe a 2025 porque los logs y el esquema B de tickets solo existen en 2025, y 2025 tuvo cambios de régimen (precio en abril, app 5.2.0 en septiembre). El historial desde 2023 (26.308 filas, 3.164 churn) se prueba como corrida de MLflow.
- **C. Uplift con el historial de contactos.** Descartado: los contactos no fueron aleatorios (se llamó a quien ya se iba), así que no se puede identificar el efecto. Queda como limitación.

### 5.2 Regla de contacto (decidido: valor esperado por cliente)

- **Elegido:** contactar si `p × 0,40 × 12 × precio_plan > 25.000`. Los umbrales implícitos son: Básico ≈ 21,8 %, Estándar ≈ 14,9 %, Premium ≈ 10,4 %, Familiar ≈ 8,7 %. Exige probabilidades calibradas.
- Descartados: un umbral único (deja valor sobre la mesa) y top-N con tope (el enunciado no da capacidad).

### 5.3 Texto de tickets (decidido: híbrido strands-decider + pysentimiento)

Se probó contra una referencia manual de los 38 textos:

| Enfoque | Resultado |
|---|---|
| strands-decider 2B: tema (8 opciones) | 38/38 ✔ |
| strands-decider 2B: amenaza de irse | 37/38 ✔ |
| strands-decider 2B: sarcasmo / frustración / "¿está molesto?" (3 redacciones) | Falla con el sarcasmo: detecta 1–3 de 10 sarcásticos ✘ |
| pysentimiento: ironía | AUC 1,00. Con 0,5 detecta 5/10, 0 falsos positivos ✔ |
| pysentimiento: emoción "ira" | Detecta 8 de 9 enojos directos ✔ |
| pysentimiento: sentimiento NEG | AUC 0,49 ✘ (el sarcasmo sale positivo) |
| NLP clásico (TF-IDF) | Descartado: con 38 textos únicos es una tabla de búsqueda. El csat sigue al tema y no al tono, así que no sirve como etiqueta débil |
| Léxico de sentimiento | Descartado: el sarcasmo lo engaña por construcción |

### 5.4 Modelos (decidido: 4 corridas)

Ver §6.3. Se descartó comparar muchas familias: con ~1.800 positivos, las diferencias entre algoritmos quedan dentro del margen de error.

### 5.5 Bonus (decidido: dashboard Streamlit, al final)

Se descartaron por ahora el agente conversacional y la combinación Next.js + Vercel. El bonus es solo un dashboard en Streamlit, si sobra tiempo.

## 6. Diseño

### 6.1 Etiquetas

- Para cada corte `d` ∈ {31-ene, 28-feb, …, 30-sep de 2025}:
  - Activos = clientes con alguna suscripción con `fecha_inicio ≤ d` y (`fecha_fin` nula o `> d`).
  - `churn_90d = 1` si el cliente no tiene ninguna suscripción activa en `d + 90 días`.
- **Comprobación obligatoria en el notebook:** comparar contra `etiquetas_entrenamiento` en los tres cortes trimestrales. Tiene que dar 100 %.
- Para puntuar: cortar al 31-dic-2025 sobre `clientes_a_puntuar`. Todos tienen `estado_actual = activo`, pero ese campo no se usa como variable.

### 6.2 Variables (todas calculadas con información disponible a la fecha `d`)

- **Cliente:** antigüedad, segmento, ciudad normalizada, edad (más indicador de edad inválida), canal de adquisición, plataforma principal.
- **Suscripción:** plan actual, precio actual, número de suscripciones previas, cambios de plan (subidas o bajadas), días en el plan actual.
- **Facturación** (facturas con `fecha_carga ≤ d`, sin recargas): mora (pagos tarde en los últimos 3 y 6 meses, facturas vencidas sin pagar a `d`), cobros duplicados reales (cuántos y cuándo fue el último), método de pago (débito automático o no), si le tocó el aumento del Básico.
- **Uso / logs** (eventos con `ts ≤ d`): inicios de sesión en los últimos 30 y 90 días y su tendencia (30 contra los 60 previos), días desde el último uso, funcionalidades distintas usadas, tasa de errores, número de `CRASH_ON_START`, si usa la 5.2.0.
- **Tickets** (`fecha ≤ d`): conteo por tema en los últimos 30 y 90 días, tickets "molestos", amenazas de irse, tickets abiertos sin resolver, csat promedio, días desde el último ticket.
- **Contactos de retención:** solo con fecha ≤ `d` (ver §9).
- Clientes sin eventos o sin tickets: conteos en 0 y un indicador de "sin actividad registrada".

### 6.3 Modelado, validación y MLflow

- **Validación hacia atrás en 3 cortes:** evaluar en jul, ago y sep de 2025. Cada uno se entrena solo con cortes cuya ventana de 90 días cierra antes del corte evaluado, o sea, cortes ≤ `d_eval − 3 meses`. Ejemplo: evaluar en jul-31 entrenando con ene-31 a abr-30.
- Las filas del mismo cliente se repiten entre cortes. Si se hace validación cruzada dentro del entrenamiento (para hiperparámetros), se agrupa por cliente.
- **Métricas en cada fold**, más su promedio y dispersión:
  - AUC-PR y AUC (capacidad de ordenar).
  - Brier y curva de calibración (calidad de las probabilidades).
  - **Valor en pesos de la regla** aplicada al fold, comparado con dos referencias: "no contactar a nadie" y "contactar a todos".
- **Corridas MLflow** (local, en Colab, sin servidor): parámetros, métricas y modelo como artefacto. Tabla final con `mlflow.search_runs()`.
  1. **Base:** regresión logística con pocas variables (antigüedad, plan, mora, tickets).
  2. **Principal:** gradient boosting (LightGBM o el `HistGradientBoosting` de scikit-learn; lo elige el builder) con todas las variables.
  3. **El principal sin variables de texto ni logs:** mide el aporte de los datos no estructurados.
  4. **El principal con el historial desde 2023:** mide si la historia antigua aporta o confunde. *[Decisión de Claude]* En los cortes de 2023–2024, las variables de logs y de tickets del esquema B quedan en nulo, con un indicador `fuente_disponible`. Los tickets del esquema A sí existen esos años y se usan. Se evalúa en los mismos folds de 2025 que las otras corridas, para que la comparación sea directa. La lectura correcta es "más historia con variables parciales contra menos historia con todas las variables".
- **Criterio de elección:** el valor promedio en pesos en los folds. Con empate dentro del margen, gana el más simple.
- **Recalibración:** el churn subió durante 2025 (11 % → 16–17 %). La calibración final se ajusta con los cortes más recientes (el builder elige el método, ver §9). El modelo final se reentrena con todos los cortes disponibles (ene–sep) antes de puntuar dic-31.
- **Interpretabilidad:** importancia de variables a nivel global y principales factores por cliente (por ejemplo, SHAP), para el memo y para el dashboard.

### 6.4 Pipeline de tickets

1. Unificar los dos esquemas (§4).
2. Extraer los textos únicos de cliente (hoy son 38).
3. **strands-decider** (`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`, vía `strands-decider serve` + POST `/v1/systemone`) responde dos preguntas:
   - `tema`: choice entre cobro_doble, cobro_no_reconocido, aumento_precio, app_se_cierra, lentitud, acceso_cuenta, cambio_plan y cancelar.
   - `amenaza`: noul "¿quiere cancelar o amenaza con hacerlo?".
   - Se guarda la confianza de cada respuesta.
4. **pysentimiento** (`lang="es"`) da `ironia` (P(ironic)) e `ira` (emoción == anger).
5. `molesto = ira OR ironía > 0,5`. El corte de 0,5 es el natural del modelo, no uno ajustado a los 38 textos.
6. **El candidato revisa a mano** la tabla de 38 filas y corrige lo que haga falta (va a la bitácora).
7. El resultado se guarda como **CSV versionado en el repo** (por ejemplo, `data_derivada/tickets_clasificados.csv`). *[Decisión de Claude]* Se indexa por **SHA-256 del texto normalizado** y **no incluye los textos literales**, para no publicar datos en el repo público. El notebook calcula el hash de cada ticket y hace el join. Por defecto carga el CSV, con un flag `RECALCULAR_NLP = False` para regenerarlo. Así el notebook corre sin GPU, sin claves y siempre da el mismo resultado.
8. *[Decisión de Claude]* `RECALCULAR_NLP = True` tiene que funcionar **en Colab**: GPU opcional (son 38 textos), con `strands-decider serve` en segundo plano dentro de la celda. strands-decider y pysentimiento van en una celda `pip install` condicional, no en la ruta por defecto.
9. Los textos que no estén en el CSV (en producción) se clasifican en vivo, y los de confianza baja van a revisión humana.

Los scripts y resultados de las pruebas (la referencia manual de 38 textos, las salidas de strands-decider y pysentimiento) están copiados en `docs/superpowers/spikes/`. Son material de apoyo para la revisión y la bitácora. *[Decisión de Claude]* Esa carpeta **no se sube al repo público**, porque contiene los textos literales.

### 6.5 Decisión de negocio y valor

- Aplicar la regla de §5.2 a `p` calibrada → `contactar`.
- **"Mensualidad actual" = precio de lista del plan vigente.** Verificado: en la factura de dic-2025, los 1.629 registros de clientes a puntuar facturan exactamente el precio de lista (Básico 23.900, Estándar 34.900, Premium 49.900, Familiar 59.900). No hay descuentos ni clientes que sigan en 19.900. El notebook lo vuelve a comprobar.
- **Valor esperado de la campaña** = Σ sobre los contactados de (`p × 0,4 × 12 × precio − 25.000`). Se reporta junto con el número de contactados, por plan y segmento.
- **Validación retrospectiva:** el valor *realizado* de la regla en los folds de validación, usando el churn real.
- **Sensibilidad:** cómo cambian el valor y el número de contactados si la efectividad es 20 % o 60 % en vez de 40 %. Prepara para el cambio en vivo.
- **Nota abierta:** los clientes con ticket "cancelar" tienen 100 % de churn tras el ticket. Hay que discutir en el memo si una llamada a esos clientes rinde el 40 % supuesto.

### 6.6 Análisis pendiente: efecto de los llamados en las etiquetas

Las etiquetas reflejan la política de llamados de entonces. Se hará un análisis de impacto **corrigiendo y sin corregir** (por ejemplo, excluyendo o reponderando a los clientes contactados dentro de la ventana) y se decide con números. El candidato definirá el diseño concreto más adelante. *[Decisión de Claude]* Como el resultado puede cambiar las filas de entrenamiento, este análisis va **antes de elegir el modelo final y de generar `predicciones.csv`**, y no al final.

### 6.7 Hallazgo abierto

- **Principal — la app 5.2.0 (solo Android) está echando clientes.**
  - Salió en sep-2025. ~50 % de sus eventos son errores (`CRASH_ON_START`), contra ~2 % en la versión 5.1.3.
  - Churn en el corte de sep: 28 % entre quienes usan la 5.2.0, contra 10 % del resto.
  - Churn en Android: 16 % (jun) → 22 % (sep). iOS: 11 % → 8 %.
  - ~630 tickets de "la app se cierra desde la actualización".
  - Acción: revertir o corregir, y priorizar el contacto a los afectados.
- **Apoyo 1 — hay cobros dobles reales.** El 100 % de los clientes con ticket de cobro doble tiene una factura duplicada con id distinto. Los duplicados crecen (107 → 435 → 805 por año). El churn tras ese ticket es 32 %, y ~46 % si el mensaje es sarcástico. Acción: corregir la facturación y reembolsar de forma proactiva.
- **Apoyo 2 — retención reactiva.** De 930 contactados, el 96 % canceló igual. La llamada ocurre ~11 días antes de la baja. Advertencia: el 96 % está sesgado porque se llamó a quien ya se iba. No prueba que la oferta falle, sino que el momento de la llamada es malo. Acción: contactar de forma proactiva, con 60 a 90 días de anticipación, y medir con un grupo de control.
- Todos estos números se recalculan en el notebook. Los de este documento vienen de la exploración preliminar.

### 6.8 Producción (media página en el notebook o en el README)

- Puntaje mensual el día 1, con los datos cargados a esa fecha.
- Reentrenar cada trimestre o cuando salte una alarma.
- Vigilar: cambios en las variables clave, churn real frente al predicho por plan y plataforma, calibración, valor realizado frente al esperado, retraso de `fecha_carga` y textos de tickets nuevos no cubiertos.
- Desconfiar ante: nuevas versiones de la app o cambios de precio (cambio de régimen), contaminación de etiquetas por los propios llamados, y caídas de cobertura de logs o tickets.
- Grupo de control aleatorio para medir la efectividad real del contacto (hoy el 40 % es un supuesto).

### 6.9 Entregables

- **`solucion.ipynb`:** corre de principio a fin en Colab, con las salidas guardadas. Orden: carga → calidad de datos → etiquetas → variables → texto → modelado/MLflow → decisión → hallazgos → producción → exportar `predicciones.csv`. Puede apoyarse en módulos `.py`.
- **`MEMO.md`:** una página, sin jerga. Qué hacer, impacto esperado en pesos y limitaciones.
- **`BITACORA_IA.md`:** momentos clave del uso de IA (qué se pidió, qué se aceptó, qué se rechazó o corrigió y por qué) y las horas invertidas. Material ya disponible:
  - El cambio de A a B en datos de entrenamiento, por insistencia del candidato, y la verificación de etiquetas al 100 %.
  - La prueba de strands-decider y su falla con el sarcasmo.
  - El cambio a pysentimiento.
  - El rechazo de un corte ajustado a mano.
  - La aclaración de que el código del dashboard lo escribió Claude.
- **`README.md`:** estructura, cómo ejecutar, botón "Open in Colab" y enlace al dashboard si existe.
- **`requirements.txt`:** solo lo que no trae Colab (por ejemplo, mlflow, lightgbm si hace falta, pysentimiento y strands-decider solo para recalcular).
- **`predicciones.csv`.**

### 6.10 Bonus — dashboard Streamlit (último paso, si sobra tiempo; lo escribe Claude)

- Publicado en Streamlit Community Cloud, sin claves.
- Lee solo artefactos exportados por el notebook: `predicciones.csv` más un archivo derivado con plan, segmento, plataforma, valor esperado y principales factores por cliente. No usa las tablas originales.
- Vistas:
  - Resumen de la campaña (valor esperado, contactados por plan y segmento).
  - Lista de a quién llamar, ordenada por valor esperado, con filtros.
  - Ficha por cliente con sus factores de riesgo.
  - Un control para cambiar los supuestos (costo, efectividad) y ver cómo cambia la lista. Esto también sirve para el cambio en vivo.

## 7. Orden de trabajo sugerido

Datos y etiquetas (parte 1) → variables, incluidos texto y logs (parte 4) → corridas de modelado con MLflow (parte 2) → análisis de §6.6 → elección del modelo final y decisión (parte 3) → `predicciones.csv` → hallazgo (5) → producción (6) → memo y bitácora → bonus.

## 8. Riesgos conocidos

- Los cambios de régimen (precio, 5.2.0) hacen que enero de 2026 pueda parecerse poco a lo que vio el entrenamiento.
- Los 113 clientes a puntuar dados de alta después de sep-30 tienen poca historia.
- La referencia manual de tickets es chica (38 textos, 10 sarcásticos) y la armó Claude. Tiene que revisarla el candidato.
- strands-decider es experimental (labs) y solo expone CLI/HTTP. Mitigación: los resultados quedan cacheados en un CSV.
- La señal "ticket cancelar = 100 % churn" puede dominar el modelo y ser poco accionable.

## 9. Lo que queda a criterio del builder

- Biblioteca de gradient boosting y sus hiperparámetros (con búsqueda modesta).
- Método de calibración (Platt o isotónica) y qué cortes recientes usar para ajustarlo.
- Tratamiento exacto de los contactos de retención previos al corte: usarlos como variable o excluirlos. Lo que no se negocia es que nunca entren contactos posteriores al corte.
- Ventanas exactas de las variables (30/90 días u otras) y la selección final de variables.
- Estructura de módulos `.py`.
