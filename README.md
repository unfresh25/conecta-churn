# Conecta+ · ¿A quién contactar y por qué se van?

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/unfresh25/conecta-churn/blob/main/solucion.ipynb)

Solución de la prueba técnica de Ciencia de Datos (nivel Senior): un modelo de churn a 90 días, la decisión de a quién contactar con la economía del enunciado y los hallazgos que explican por qué se van los clientes.

## Resultados en 30 segundos

- **Hallazgo principal:** la versión 5.2.0 de la app (solo Android, desde el 1-sep-2025) se cierra al abrir. Sus usuarios tienen 28 % de churn a 90 días, contra 11 % de los usuarios de Android en la versión anterior. Hay además cobros dobles reales y crecientes, y una retención que llama demasiado tarde (el 98 % de los contactados se va igual).
- **Datos no estructurados:** los logs y el texto de los tickets duplican el valor del modelo (13,1 M contra 6,0 M COP al mes en el backtest, mismo modelo con y sin esas variables).
- **Decisión:** contactar a 634 de 1.556 clientes (`predicciones.csv`). Con el 40 % de efectividad del enunciado, eso da ~16 M COP netos. Ese 40 % no está probado, así que se recomienda un piloto con grupo de control.
- Resumen para gerencia: [`MEMO.md`](MEMO.md). Uso de IA y horas: [`BITACORA_IA.md`](BITACORA_IA.md).

## Cómo ejecutarlo

**En Colab (recomendado).**
1. Abrir el notebook con el botón de arriba.
2. Subir `datos_conecta.zip` al panel de archivos de Colab (en `/content/`). También se puede leer desde Drive: hay que descomentar dos líneas de la celda de entorno.
3. Ejecutar *Entorno de ejecución → Ejecutar todo*. Tarda entre 5 y 10 minutos.

La primera celda clona este repositorio para tener el paquete `conecta/` e instala `requirements.txt` (solo MLflow; el resto ya viene en Colab).

**En local.**
```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
# copiar datos_conecta.zip a la raíz del repo
.venv/bin/jupyter lab solucion.ipynb
.venv/bin/pytest -q               # 68 pruebas: fugas de información, etiquetas, economía, contrato de predicciones
```
En macOS, LightGBM necesita `brew install libomp`.

**MLflow.** Las corridas se registran en `mlflow.db` (SQLite). El backend de archivos `./mlruns` está en mantenimiento en MLflow 3. Para verlas:
`mlflow ui --backend-store-uri sqlite:///mlflow.db`.

**Texto de los tickets.** La clasificación (tema, amenaza de irse, ironía y enojo) se guarda en `data_derivada/tickets_clasificados.csv`. Ese archivo va indexado por un hash del texto, **sin textos de clientes**, y el notebook lo usa por defecto. Para regenerarlo, en la sección 3 hay que poner `RECALCULATE_NLP = True`. Eso requiere `pysentimiento` y un servidor local de `strands-decider` (Python ≥ 3.12).

## Estructura

```
solucion.ipynb               notebook principal (orquesta y explica; salidas guardadas)
conecta/
  data.py                    carga y limpieza (ciudades, edades, facturas recargadas, cobros dobles, zona horaria)
  tickets.py                 unificación de los dos esquemas de tickets y clasificación del texto
  labels.py                  churn a 90 días reconstruido desde suscripciones (reproduce el 100 % de las etiquetas)
  features.py                variables a la fecha de corte, sin fugas
  validation.py              folds temporales con 3 meses de separación
  business.py                economía del contacto, regla por plan, punto de equilibrio
  models.py                  modelos, backtest con valor en pesos, MLflow, contrato de predicciones
  retention.py               desenlace de las llamadas de retención
tests/                       pruebas con pytest
data_derivada/               clasificación de tickets cacheada (sin textos)
predicciones.csv             cliente_id, probabilidad, contactar (1.556 filas)
MEMO.md · BITACORA_IA.md
docs/superpowers/            diseño y plan de implementación
```

## Decisiones principales

| Tema | Decisión | Por qué |
|---|---|---|
| Datos de entrenamiento | Cortes mensuales reconstruidos (mar-2023 a sep-2025) | La regla reproduce el 100 % de las etiquetas entregadas; da 5 veces más filas |
| Validación | Backtest en jul, ago y sep de 2025, entrenando solo con cortes de 3 meses antes o más | Un cliente aparece en varios cortes y el churn cambia en el tiempo: la validación aleatoria engaña |
| Métrica de selección | Valor realizado en pesos | La decisión es económica; el AUC no la mide |
| Modelo | LightGBM con parámetros fijos, sin variables de contacto ni recalibración | Ganó en el backtest. El ajuste anidado de hiperparámetros empeoraba el valor. Las variables de contacto dependen de la política actual |
| Llamadas de retención | No se corrigen las etiquetas y no se contacta a quien ya está en proceso de baja | La contaminación es < 1 %; excluir a los llamados borra la mitad de los casos de churn |

Los datos no están en el repositorio.
