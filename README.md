# Conecta+ · ¿A quién contactar y por qué se van?

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/unfresh25/conecta-churn/blob/main/solucion.ipynb)

Solución de la prueba técnica de Ciencia de Datos (nivel Senior): un modelo de churn a 90 días, la decisión de a quién contactar con la economía del enunciado y los hallazgos sobre por qué se van los clientes.

## Resultados

- La versión 5.2.0 de la app (solo Android, desde el 1-sep-2025) se cierra al abrir. Sus usuarios tienen 28 % de churn a 90 días, contra 11 % de los usuarios de Android que siguen en la versión anterior. Además hay cobros dobles reales y en aumento, y la retención llama demasiado tarde: el 98 % de los contactados se va igual.
- Los logs y el texto de los tickets duplican el valor del modelo: 13,1 M contra 6,0 M COP al mes en el backtest, con el mismo modelo con y sin esas variables.
- `predicciones.csv` marca a 634 de 1.556 clientes para contactar. Con el 40 % de efectividad del enunciado eso rinde ~16 M COP netos, pero ese 40 % no está probado, así que propongo un piloto con grupo de control.
- El resumen para gerencia está en [`MEMO.md`](MEMO.md), y el uso de IA y las horas en [`BITACORA_IA.md`](BITACORA_IA.md).

## Cómo ejecutarlo

En Colab:
1. Abrir el notebook con el botón de arriba.
2. Subir `datos_conecta.zip` al panel de archivos de Colab, en `/content/`. Para leerlo desde Drive hay que descomentar dos líneas de la celda de entorno.
3. Ejecutar *Entorno de ejecución → Ejecutar todo*. Tarda entre 5 y 10 minutos.

La primera celda clona este repositorio para tener el paquete `conecta/` e instala `requirements.txt`, que solo trae MLflow; el resto ya viene en Colab.

En local:
```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
# copiar datos_conecta.zip a la raíz del repo
.venv/bin/jupyter lab solucion.ipynb
.venv/bin/pytest -q
```
En macOS, LightGBM necesita `brew install libomp`. Las 51 pruebas cubren la limpieza de datos, la reconstrucción de las etiquetas, los folds temporales, algunas reglas contra fugas (contactos, tickets y csat posteriores al corte), la economía y el formato de las predicciones.

Las corridas de MLflow se guardan en `mlflow.db` (SQLite), porque MLflow 3 dejó en mantenimiento el backend de archivos. Para verlas: `mlflow ui --backend-store-uri sqlite:///mlflow.db`.

La clasificación del texto de los tickets (tema, amenaza de irse, ironía y enojo) está en `data_derivada/tickets_clasificados.csv`, indexada por un hash del texto y sin textos de clientes. El notebook la usa por defecto. Para regenerarla hay que poner `RECALCULATE_NLP = True` en la sección 3, lo que requiere `pysentimiento` y un servidor local de `strands-decider` (Python 3.12 o posterior).

## Estructura

```
solucion.ipynb               notebook principal, con salidas guardadas
conecta/
  data.py                    carga y limpieza (ciudades, edades, facturas recargadas, cobros dobles, zona horaria)
  tickets.py                 unificación de los dos esquemas de tickets y clasificación del texto
  labels.py                  churn a 90 días reconstruido desde suscripciones
  features.py                variables a la fecha de corte, sin fugas
  validation.py              folds temporales con 3 meses de separación
  business.py                economía del contacto, regla por plan y punto de equilibrio
  models.py                  modelos, backtest con valor en pesos, MLflow y validación de predicciones
  retention.py               desenlace de las llamadas de retención
tests/                       pruebas con pytest
data_derivada/               clasificación de tickets cacheada, sin textos
predicciones.csv             cliente_id, probabilidad, contactar (1.556 filas)
MEMO.md · BITACORA_IA.md
docs/superpowers/            diseño y plan de implementación
```

## Decisiones principales

| Tema | Decisión | Motivo |
|---|---|---|
| Datos de entrenamiento | Cortes mensuales reconstruidos, de marzo de 2023 a septiembre de 2025 | La regla reproduce el 100 % de las etiquetas entregadas y da 5 veces más filas |
| Validación | Backtest en julio, agosto y septiembre de 2025, entrenando solo con cortes de 3 meses antes o más | Un cliente aparece en varios cortes y el churn cambia en el tiempo, así que la validación aleatoria sobreestima el desempeño |
| Métrica de selección | Valor realizado en pesos | La decisión es económica y el AUC no la mide |
| Modelo | LightGBM con parámetros fijos, sin variables de contacto y sin recalibrar | Ganó en el backtest; el ajuste anidado de hiperparámetros empeoraba el valor, y las variables de contacto dependen de la política actual |
| Llamadas de retención | Las etiquetas no se corrigen y no se contacta a quien ya está en proceso de baja | La contaminación es menor al 1 %, y excluir a los llamados borra la mitad de los casos de churn |

Los datos no están en el repositorio.
