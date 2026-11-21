# Bitácora de uso de IA

## Cómo se repartió el trabajo

- **Herramienta:** Claude Code (modelo Claude Opus), en una sesión local con el repositorio. Los modelos de texto (strands-decider 2B y pysentimiento) corrieron en local, sin API keys.
- **Reparto:** Claude propuso enfoques y **escribió el código**: módulos de `conecta/`, pruebas, notebook y documentos. Yo decidí cada punto de diseño, revisé el trabajo en cuatro pausas acordadas (después de las etiquetas, las variables, el modelado y las predicciones) y pedí correcciones o análisis adicionales.
  - Al principio el plan era que yo escribiera el código. Lo cambié el 20-nov para usar el tiempo en revisar y decidir. Esta bitácora lo declara tal cual.
- **Reglas que fijé:** identificadores de código en inglés, ninguna línea de coautoría de la IA en los commits, nada de datos de clientes en el repositorio y todo ejecutable gratis en Colab.

## Momentos clave

| # | Qué se pidió o propuso | Qué se aceptó, rechazó o corrigió, y por qué |
|---|---|---|
| 1 | Claude propuso entrenar solo con las 3 etiquetas entregadas (4.693 filas). | **Rechazado por mí.** Insistí en reconstruir el churn mensual desde `suscripciones`. Antes de usarlo pedí verificar la regla: reproduce el **100 %** de las etiquetas entregadas. Con eso hay 13.600 filas en 2025 y 26.308 desde 2023, en lugar de 4.693. |
| 2 | Regla de contacto: umbral único, top-N o valor esperado por cliente. | Elegí **valor esperado por cliente** (umbral por plan). Agregué la pregunta de si las llamadas pasadas contaminan las etiquetas, que después se convirtió en la sección 6. |
| 3 | Clasificar el texto de los tickets. Yo propuse probar strands-decider. | Lo corrió Claude contra 38 textos etiquetados a mano: tema 38/38 y amenaza de irse 37/38, pero **falló con el sarcasmo**, incluso cambiando la pregunta. |
| 4 | Detectar el sarcasmo. | Propuse un modelo de NLP dedicado. Claude probó **pysentimiento** (ironía + emoción): 13 de 18 molestos con 1 falso positivo. Se quedó un esquema híbrido. |
| 5 | Corte de ironía. | **Rechazado un corte ajustado a mano** a los 38 textos, porque sería sobreajustar a la referencia. Se usa el corte natural del modelo (0,5). |
| 6 | Revisión humana de la clasificación: 7 textos donde el modelo y la referencia no coinciden (4 sarcasmos no detectados, 1 enojo en un reclamo de precio, 1 "bajar de plan" leído como amenaza). | Decidí **no corregirlos a mano**: el CSV es la salida reproducible del modelo, y los desacuerdos quedan como evidencia de sus límites. |
| 7 | Cuatro corridas en MLflow: base, LightGBM completo, sin datos no estructurados e historial desde 2023. | Aceptado. El resultado **contradijo dos expectativas del diseño**: ganó el historial desde 2023 (3 de 3 meses) y la recalibración no ayudó. Apliqué la regla de selección fijada antes de ver los resultados, sin acomodarla a lo que esperaba. |
| 8 | Claude escribió en el notebook que el historial "no gana en todos los meses" y que el modelo final "subestima" el churn. | **Corregido** al verificar con los números: ambas afirmaciones eran falsas. También se corrigieron cifras preliminares del diseño, como los duplicados por año (107/435/805 contaban copias de facturas recargadas; los reales son 47/224/428). |
| 9 | Pregunté si el modelo es mejor que lo que hace hoy el equipo de retención. | Llevó a comparar contra la política actual y calcular el **punto de equilibrio**: el equipo necesita retener 6 % y retiene ~3 %; el modelo necesita ~21 %. De ahí sale la propuesta del **piloto con grupo de control**. |
| 10 | Pregunté si se ajustaron hiperparámetros. | No se habían ajustado. Pedí probarlo bien: con un ajuste anidado, sin mirar los meses de evaluación, el valor **empeora** (10,3 M contra 13,9 M al mes). Se mantienen los parámetros fijos y queda documentado. |
| 11 | Pedí analizar el efecto de las llamadas antes de decidir el modelo final. | Claude encontró que la llamada es parte del proceso de baja (siempre 3 a 19 días antes) y que había clientes censurados contados como "retenidos". Aprobé tres decisiones: no corregir las etiquetas (excluir a los llamados borraba la mitad de los casos de churn), quitar las variables de contacto del modelo y no contactar a quien ya está en proceso de baja. |
| 12 | Bonus: propuse un dashboard con agente conversacional en Next.js. | Lo reduje a un dashboard en Streamlit, como último paso y solo si sobra tiempo. Si existe, el código lo escribió Claude. |

## Qué revisé yo personalmente

- La regla de etiquetas y su verificación al 100 %.
- Las reglas contra fugas de información: cada variable con su prueba en `tests/test_features.py`.
- La regla de selección de modelos y cada punto de decisión de negocio.
- Los textos con desacuerdo de la clasificación.
- Las cifras del memo contra las salidas del notebook.

## Horas invertidas

> Completar con los tiempos reales antes de entregar.

| Etapa | Horas |
|---|---|
| Lectura del enunciado, exploración y diseño | _ |
| Pruebas de NLP (strands-decider, pysentimiento) | _ |
| Revisión de datos, etiquetas y variables | _ |
| Modelado, análisis de llamadas y decisión | _ |
| Hallazgos, memo y documentación | _ |
| **Total** | _ |
