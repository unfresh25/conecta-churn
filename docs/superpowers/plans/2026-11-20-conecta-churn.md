# Conecta+ Churn — Plan de implementación

> **Para quien ejecuta:** Claude escribe el código siguiendo este plan, tarea por tarea. El candidato revisa, adapta o pide correcciones en las pausas de revisión. Toda mención a "tu criterio" o "decisión tuya" se decide con el candidato. Los pasos usan casillas (`- [ ]`).
>
> **Entorno:** se desarrolla y ejecuta en local, con Python 3.12 y versiones fijadas para imitar Colab. El notebook se ejecuta en local con `jupyter nbconvert --execute`. La comprobación final en Colab (Tarea 13) la hace el candidato, porque Claude no tiene acceso a Colab. Lo específico de Colab (ruta `/content`, `git clone`, Drive) va protegido con `if "google.colab" in sys.modules`.

**Objetivo:** un repo público en GitHub con un notebook que corre en Colab de principio a fin y produce `predicciones.csv` (probabilidad de churn a 90 días y decisión de contacto para 1.556 clientes), junto con MLflow, hallazgos, producción, `MEMO.md` y `BITACORA_IA.md`.

**Arquitectura:** la lógica vive en un paquete `conecta/` con funciones puras y probadas con pytest sobre datos sintéticos pequeños. El notebook `solucion.ipynb` solo orquesta, muestra y explica. Todas las variables se calculan "a la fecha de corte" mediante funciones `(datos, corte, clientes) -> DataFrame`, y se apilan en un panel de cortes mensuales de 2025. La clasificación NLP de tickets se calcula aparte y se cachea en un CSV indexado por hash.

**Stack:** Python 3.12 (Colab), pandas, numpy, scikit-learn, lightgbm (viene en Colab), mlflow, shap, pytest. Opcional, solo para recalcular NLP: strands-decider, pysentimiento. Bonus: streamlit.

**Spec:** `docs/superpowers/specs/2026-11-20-conecta-churn-design.md`. Léelo antes de cada tarea: los porqués están ahí.

## Restricciones globales

- Fecha "hoy" = `2025-12-31`. Horizonte = 90 días.
- Cortes de entrenamiento: fin de mes de `2025-01-31` a `2025-09-30`. Folds de evaluación: `2025-07-31`, `2025-08-31`, `2025-09-30`, con separación de 3 meses.
- Economía: `COSTO_CONTACTO = 25_000`, `EFECTIVIDAD = 0.40`, `MESES_VALOR = 12`. `PRECIOS = {"Basico": 23_900, "Estandar": 34_900, "Premium": 49_900, "Familiar": 59_900}`. Los nombres de plan coinciden con los valores de `suscripciones.plan`.
- Regla: contactar si `p × EFECTIVIDAD × MESES_VALOR × precio > COSTO_CONTACTO`, con desigualdad estricta.
- Prohibido como variable: `clientes.estado_actual`. Prohibido cualquier dato con fecha posterior al corte: eventos `ts`, tickets `fecha`, facturas `fecha_carga`, contactos `fecha_contacto_retencion`.
- Fechas de tickets y eventos: se pasan a hora local `America/Bogota` y luego a fecha sin zona antes de comparar con el corte. Un evento cuenta en el corte `d` si su fecha local es ≤ `d`.
- Nada de datos crudos en el repo. `.gitignore` incluye `datos/`, `*.zip`, `mlruns/` y `docs/superpowers/spikes/`. El CSV de tickets clasificados no lleva textos.
- `predicciones.csv` va en la raíz, con columnas exactas `cliente_id,probabilidad,contactar` y 1.556 filas.
- El notebook carga `datos_conecta.zip` desde `/content` o desde Drive, como `inicio.ipynb`, y corre sin claves ni GPU.
- Idioma: nombres de funciones y comentarios en español, sin tildes en los identificadores.

## Foco de revisión

1. **Clientes sin historia** (los 113 dados de alta después de sep-30, o sin eventos ni tickets): las variables tienen que salir en 0 o NaN con indicador, nunca romper ni desaparecer de la matriz. Pruebas en Tarea 5.
2. **Borde de zona horaria:** un ticket del `2025-09-30T23:30:00-05:00` cuenta para el corte sep-30. El mismo instante escrito en UTC (`2025-10-01T04:30:00Z`) también. Pruebas en Tareas 2 y 5.
3. **Tickets con cliente nulo o ilegible** (`customer` vacío o con formato raro): se descartan con un conteo reportado, sin romper. Prueba en Tarea 2.
4. **Texto de ticket que no está en el CSV de clasificación** (un texto nuevo): las variables NLP de ese ticket quedan NaN y se reporta el conteo, sin error. Prueba en Tarea 5.
5. **`predicciones.csv` inválido:** ids faltantes o duplicados, NaN, probabilidades fuera de [0, 1], o `contactar` distinto de 0/1. Un validador falla con un mensaje claro. Prueba en Tarea 10.

---

## Estructura de archivos

```
README.md  solucion.ipynb  requirements.txt  predicciones.csv  MEMO.md  BITACORA_IA.md  .gitignore  pytest.ini
conecta/__init__.py
conecta/datos.py        # carga y limpieza (clientes, suscripciones, facturas, eventos)
conecta/tickets.py      # unificación de esquemas, hash, clasificación NLP y caché
conecta/etiquetas.py    # activos_en, construir_etiquetas, cortes_mensuales
conecta/variables.py    # variables a la fecha de corte y construir_panel
conecta/validacion.py   # folds temporales con separación
conecta/negocio.py      # constantes económicas, umbral, valor esperado, decisión
conecta/modelos.py      # pipelines, calibración, evaluación por fold, MLflow
data_derivada/tickets_clasificados.csv
tests/conftest.py  tests/test_datos.py  tests/test_tickets.py  tests/test_etiquetas.py
tests/test_variables.py  tests/test_validacion.py  tests/test_negocio.py  tests/test_predicciones.py
dashboard/app.py  dashboard/requirements.txt          # bonus (Claude)
```

En Colab, la primera celda clona el repo si `conecta/` no existe (`!git clone <url-del-repo>`), agrega la ruta a `sys.path` y descomprime el zip en `datos/`.

---

### Task 0 —: Esqueleto del repo

**Archivos:**
- Crear: `.gitignore`, `pytest.ini` (`testpaths = tests`), `requirements.txt` (mlflow, shap, pytest), `conecta/__init__.py`, `tests/conftest.py`

**Interfaces:**
- Produce: fixtures de pytest en `conftest.py` con DataFrames sintéticos mínimos que imitan cada tabla (mismas columnas y tipos que en `conecta.db`): `subs_df`, `facturas_df`, `eventos_df`, `clientes_df`, `tickets_raw` (lista de dicts con un registro de cada esquema). Las tareas siguientes les agregan filas a medida que las necesitan.

- [ ] **Paso 1:** `git init`, rama `main`. Crear los archivos de arriba. El `.gitignore` sigue las restricciones globales.
- [ ] **Paso 2:** crear un entorno local (Python 3.12) e instalar `pandas scikit-learn lightgbm mlflow shap pytest`.
- [ ] **Paso 3:** `pytest` → esperado: "no tests ran" y salida 5, sin errores de importación.
- [ ] **Paso 4:** commit `chore: esqueleto del repo`.

---

### Task 1 —: Carga y limpieza

**Archivos:**
- Crear: `conecta/datos.py`
- Probar: `tests/test_datos.py`

**Interfaces:**
- Produce:
  - `@dataclass Datos`: `clientes, suscripciones, facturas, etiquetas, a_puntuar, eventos: pd.DataFrame`; `tickets_raw: list[dict]`; `tickets: pd.DataFrame | None = None` (se llena en la Tarea 2).
  - `cargar_datos(ruta: str | Path) -> Datos` lee `conecta.db`, `tickets.jsonl` (crudo, en `tickets_raw`) y `eventos.jsonl.gz`.
  - `normalizar_ciudad(s: pd.Series) -> pd.Series`
  - `limpiar_edad(s: pd.Series) -> pd.Series` (float; NaN fuera de [18, 100])
  - `limpiar_facturas(f: pd.DataFrame) -> pd.DataFrame` agrega la columna bool `es_cobro_duplicado`
  - `limpiar_eventos(e: pd.DataFrame) -> pd.DataFrame` (deduplica por `event_id` y agrega `fecha_local`)
  - `limpiar(datos: Datos) -> Datos` aplica todo lo anterior.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
def test_normalizar_ciudad_todas_las_grafias():
    entrada = pd.Series(["BOGOTA","bogota d.c.","Bogota D.C.","Bogotá","medellin","MEDELLIN","Medellín",
                         "Cali","CALI","Santiago de Cali","B/quilla","BARRANQUILLA","Barranquilla",
                         "Bucaramanga","BUCARAMANGA","Pereira","PEREIRA"])
    assert set(normalizar_ciudad(entrada)) == {"Bogotá","Medellín","Cali","Barranquilla","Bucaramanga","Pereira"}

def test_normalizar_ciudad_desconocida_queda_nan():
    assert normalizar_ciudad(pd.Series(["Tunja"])).isna().all()

def test_limpiar_edad():
    assert limpiar_edad(pd.Series([0, 999, 17, 18, 45, 100, 101])).isna().tolist() == [True,True,True,False,False,False,True]

def test_limpiar_facturas_recarga_vs_cobro_doble():
    # mismo factura_id cargado dos veces -> queda 1 fila (la de fecha_carga más temprana), es_cobro_duplicado=False
    # mismo (cliente, periodo, suscripcion) con factura_id distinto -> quedan 2 filas; la de id mayor tiene es_cobro_duplicado=True
    ...  # con filas sintéticas explícitas; afirmar len y la columna

def test_limpiar_eventos_dedup_y_fecha_local():
    # dos filas con el mismo event_id -> 1; ts "2025-10-01T04:30:00Z" -> fecha_local == 2025-09-30
    ...
```

- [ ] **Paso 2:** `pytest tests/test_datos.py -v` → esperado: FALLA (ImportError).
- [ ] **Paso 3:** implementar. `normalizar_ciudad`: pasar a minúsculas, quitar tildes y puntuación, y mapear con un diccionario explícito. `limpiar_facturas`: primero `drop_duplicates("factura_id")` ordenando por `fecha_carga`, luego marcar con `duplicated(["cliente_id","periodo","suscripcion_id"])`. Fechas a `datetime64`.
- [ ] **Paso 4:** `pytest tests/test_datos.py -v` → esperado: PASA.
- [ ] **Paso 5:** comprobar en el notebook (sección "Calidad de datos") con los datos reales, y dejar la tabla de problemas con sus conteos. Esperado: 6 ciudades, 65 edades en NaN, 677 recargas eliminadas, 699 cobros duplicados marcados y 1.616 eventos duplicados eliminados. Si un conteo difiere, investigar antes de seguir.
- [ ] **Paso 6:** commit `feat: carga y limpieza de datos`.

---

### Task 2 —: Unificación de tickets

**Archivos:**
- Crear: `conecta/tickets.py`
- Probar: `tests/test_tickets.py`

**Interfaces:**
- Consume: `Datos.tickets_raw` (Tarea 1).
- Produce:
  - `unificar_tickets(registros: list[dict]) -> tuple[pd.DataFrame, int]`. Devuelve un DataFrame con las columnas `ticket_id, cliente_id (Int64), fecha (datetime local sin zona), canal, tema_origen, texto, estado ("abierto"|"cerrado"), fecha_resolucion, csat (float), esquema ("A"|"B")`, más el número de registros descartados.
  - `hash_texto(texto: str) -> str`: SHA-256 en hex de `unicodedata.normalize("NFC", texto.strip())`.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
def test_unificar_esquema_A(tickets_raw):   # customer "CL-012375" -> 12375; status closed -> "cerrado"; tema_origen = category
def test_unificar_esquema_B(tickets_raw):   # cliente.id "12386" -> 12386; texto = primer mensaje con autor "cliente"; estado.valor "resuelto" -> "cerrado", "abierto" -> "abierto"; csat = satisfaccion.csat o NaN; tema_origen = tipo.sub
def test_zona_horaria_borde():
    # A: created_at "2025-10-01T04:30:00Z" -> fecha.date() == date(2025,9,30)
    # B: fecha "2025-09-30T23:30:00-05:00" -> fecha.date() == date(2025,9,30)
def test_cliente_nulo_se_descarta():
    df, descartados = unificar_tickets([{"ticket_id": "TK-1", "customer": None, "text": "x", "created_at": "2025-01-01T00:00:00Z"}])
    assert len(df) == 0 and descartados == 1
def test_hash_estable():
    assert hash_texto(" Hola ") == hash_texto("Hola") and len(hash_texto("Hola")) == 64
```

- [ ] **Paso 2:** ejecutar → FALLA.
- [ ] **Paso 3:** implementar. Un parser por esquema; el esquema se detecta por la presencia de la clave `"mensajes"`.
- [ ] **Paso 4:** ejecutar → PASA.
- [ ] **Paso 5:** en el notebook: 4.452 registros de entrada, conteo por esquema (A 2.553, B 1.899), descartados y 38 textos únicos. Asignar el resultado a `datos.tickets`.
- [ ] **Paso 6:** commit `feat: unificacion de tickets`.

---

### Task 3 —: Etiquetas reconstruidas

**Archivos:**
- Crear: `conecta/etiquetas.py`
- Probar: `tests/test_etiquetas.py`

**Interfaces:**
- Consume: `Datos.suscripciones` con `fecha_inicio` y `fecha_fin` como datetime (NaT = abierta).
- Produce:
  - `cortes_mensuales(inicio: str, fin: str) -> list[pd.Timestamp]`: fines de mes, ambos extremos incluidos.
  - `activos_en(subs: pd.DataFrame, fecha: pd.Timestamp) -> set[int]`: `fecha_inicio <= fecha` y (`fecha_fin` es NaT o `> fecha`).
  - `construir_etiquetas(subs, cortes, horizonte_dias: int = 90) -> pd.DataFrame` con columnas `cliente_id, fecha_corte, churn_90d`. `churn_90d = 1` si el cliente activo en el corte no está en `activos_en(subs, corte + horizonte)`.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
def test_cortes_mensuales():
    c = cortes_mensuales("2025-01-31", "2025-09-30")
    assert len(c) == 9 and c[1] == pd.Timestamp("2025-02-28")

def test_cambio_de_plan_no_es_churn(subs_df):
    # sub1 termina 2025-02-10 con motivo cambio_plan; sub2 empieza 2025-02-10 abierta -> churn 0 en el corte 2025-01-31
def test_baja_dentro_de_ventana_es_churn(subs_df):   # fecha_fin 2025-03-15 sin otra sub -> 1
def test_fin_igual_al_corte_no_esta_activo(subs_df): # fecha_fin == corte -> no aparece en la salida
def test_alta_despues_del_corte_no_aparece(subs_df)
```

- [ ] **Paso 2:** ejecutar → FALLA.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** ejecutar → PASA.
- [ ] **Paso 5: comprobación contra los datos reales en el notebook.** Construir las etiquetas para los cortes 2025-03-31, 2025-06-30 y 2025-09-30 y unirlas con `etiquetas_entrenamiento` (outer). Afirmar: cero filas solo en uno de los dos lados y `(churn_90d_mio == churn_90d).all()`. Construir también el panel completo de ene a sep → esperado: 13.600 filas, 1.815 churn. Y comprobar que `activos_en(subs, 2025-12-31)` es igual al conjunto de `clientes_a_puntuar`.
- [ ] **Paso 6:** commit `feat: etiquetas reconstruidas y verificadas`.

---

### Task 4 —: Clasificación NLP de tickets (caché)

**Archivos:**
- Modificar: `conecta/tickets.py`
- Crear: `data_derivada/tickets_clasificados.csv`
- Probar: `tests/test_tickets.py`

**Interfaces:**
- Consume: `hash_texto` (Tarea 2). Las preguntas y los criterios de las pruebas están en `docs/superpowers/spikes/spike_decider.py` (TEMAS y las preguntas `tema` y `amenaza`) y en `spike_pysent.py`.
- Produce:
  - `TEMAS: dict[str, str]`: las 8 opciones del spec §6.4 con su descripción.
  - `regla_molesto(p_ironia: pd.Series, ira: pd.Series) -> pd.Series[bool]` = `ira | (p_ironia > 0.5)`.
  - `clasificar_textos(textos: list[str], puerto: int = 8765) -> pd.DataFrame` con columnas `hash, tema, conf_tema, p_amenaza, p_ironia, ira (bool), molesto (bool)`. Requiere `strands-decider serve` activo y pysentimiento instalado.
  - `cargar_clasificacion(ruta: str | Path) -> pd.DataFrame` con las mismas columnas, `hash` único.

- [ ] **Paso 1: escribir las pruebas que fallan** (solo de lo que no necesita los modelos)

```python
def test_regla_molesto():
    r = regla_molesto(pd.Series([0.9, 0.1, 0.5, 0.1]), pd.Series([False, True, False, False]))
    assert r.tolist() == [True, True, False, False]   # 0,5 exacto no cuenta (estricto)
def test_cargar_clasificacion_esquema(tmp_path):     # CSV con las columnas exactas; hash duplicado -> ValueError
```

- [ ] **Paso 2:** ejecutar → FALLA.
- [ ] **Paso 3:** implementar. `clasificar_textos` hace POST a `/v1/systemone` con `{"state": f'Mensaje de un cliente a soporte: "{texto}"', "questions": {"tema": ..., "amenaza": ...}}`, usando el modelo `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`. Llama a `create_analyzer(task="irony", lang="es")` y a `create_analyzer(task="emotion", lang="es")`: `ira = output == "anger"` y `p_ironia = probas["ironic"]`.
- [ ] **Paso 4:** ejecutar → PASA.
- [ ] **Paso 5:** generar el CSV una vez (localmente o en Colab) con los 38 textos únicos y guardarlo sin textos.
- [ ] **Paso 6: revisión humana.** Unir el CSV con los textos *solo en local*, revisar las 38 filas contra la referencia de `docs/superpowers/spikes/` y corregir lo que haga falta en el CSV. Anotar en `BITACORA_IA.md` cada corrección y por qué. Esperado de las pruebas: tema 38/38, amenaza 37/38, molesto 13/18 contra la referencia.
- [ ] **Paso 7:** en el notebook, una sección "Texto de tickets" con el flag `RECALCULAR_NLP = False`. En `True`, una celda instala strands-decider y pysentimiento, levanta `strands-decider serve` con `subprocess.Popen`, espera a que `/health` responda y regenera el CSV. Documentar ahí la elección, las pruebas y los límites (spec §5.3).
- [ ] **Paso 8:** commit `feat: clasificacion NLP de tickets cacheada`.

---

### Task 5 —: Variables a la fecha de corte y panel

**Archivos:**
- Crear: `conecta/variables.py`
- Probar: `tests/test_variables.py`

**Interfaces:**
- Consume: `Datos` limpio (Tareas 1 y 2), la clasificación (Tarea 4) y `construir_etiquetas` (Tarea 3).
- Produce. Cada función tiene la firma `(datos: Datos, corte: pd.Timestamp, clientes: pd.Index) -> pd.DataFrame`, indexada por `cliente_id` y con exactamente `clientes` como índice:
  - `var_cliente`: antigüedad en días, segmento, ciudad, edad, `edad_invalida`, canal, plataforma.
  - `var_suscripcion`: plan, precio, número de suscripciones previas, cambios de plan, días en el plan actual.
  - `var_facturas`: atrasos en los últimos 3 y 6 meses, vencidas sin pagar a la fecha, cobros duplicados (total y en los últimos 90 días), `debito_auto`, `afectado_aumento_basico`. Solo facturas con `fecha_carga <= corte`. Un pago con `fecha_pago > corte` cuenta como no pagado a esa fecha.
  - `var_eventos`: inicios de sesión en los últimos 30 y 90 días, tendencia, días desde el último uso, funcionalidades distintas, tasa de errores, número de `CRASH_ON_START`, `usa_520`, `sin_eventos`.
  - `var_tickets(datos, clasif, corte, clientes)`: conteos por tema en los últimos 30 y 90 días, molestos, amenazas, abiertos a la fecha, csat promedio, días desde el último ticket, `sin_tickets`. Un ticket está "abierto a la fecha" si `fecha_resolucion` es NaT o mayor que el corte.
  - `var_contactos`: `contactado_previo`, días desde el último contacto. Solo contactos con fecha `<= corte`.
  - `construir_matriz(datos, clasif, corte, clientes) -> pd.DataFrame` concatena las anteriores.
  - `construir_panel(datos, clasif, etiquetas: pd.DataFrame) -> pd.DataFrame`: una fila por (cliente, corte), con las columnas `cliente_id, fecha_corte, churn_90d` más las variables.

- [ ] **Paso 1: escribir las pruebas que fallan.** Una por fuga posible y una por caso del Foco de revisión.

```python
def test_evento_posterior_al_corte_no_cuenta(...)          # evento 2025-10-01 local -> logins_30d == 0 en el corte 2025-09-30
def test_evento_borde_zona_horaria_cuenta(...)             # ts "2025-10-01T04:30:00Z" -> cuenta en el corte 2025-09-30
def test_factura_cargada_despues_del_corte_no_cuenta(...)  # periodo 2025-09, fecha_carga 2025-10-02 -> no aparece en el corte 2025-09-30
def test_pago_posterior_al_corte_es_impago(...)            # vencida 2025-09-15, pagada 2025-10-05 -> vencidas_impagas == 1 en el corte 2025-09-30
def test_contacto_posterior_al_corte_no_cuenta(...)        # fecha_contacto 2025-10-10 -> contactado_previo == 0
def test_ticket_resuelto_despues_del_corte_esta_abierto(...)
def test_cliente_sin_historia_no_rompe(...)                # cliente sin eventos ni tickets -> está en el índice, conteos 0, sin_eventos == 1, sin_tickets == 1
def test_texto_sin_clasificacion_da_nan(...)               # hash ausente del CSV -> esas variables NaN, sin excepción
def test_estado_actual_no_es_variable(...)                 # "estado_actual" no está en construir_matriz(...).columns
def test_indice_igual_a_clientes(...)                      # construir_matriz(...).index.equals(clientes)
```

- [ ] **Paso 2:** ejecutar → FALLA.
- [ ] **Paso 3:** implementar. Cada función filtra primero por fecha ≤ corte y después agrega. Las ventanas exactas (30/90) y la selección final de variables quedan a tu criterio (spec §9).
- [ ] **Paso 4:** ejecutar → PASA.
- [ ] **Paso 5:** en el notebook, construir el panel de 2025 (13.600 filas) y la matriz de puntuación al 2025-12-31 (1.556 filas). Mostrar la tasa de nulos por columna y la tasa de churn por corte.
- [ ] **Paso 6:** commit `feat: variables a la fecha de corte y panel`.

---

### Task 6 —: Folds temporales

**Archivos:**
- Crear: `conecta/validacion.py`
- Probar: `tests/test_validacion.py`

**Interfaces:**
- Produce: `folds_temporales(cortes: list[pd.Timestamp], cortes_eval: list[pd.Timestamp], gap_meses: int = 3) -> list[tuple[list[pd.Timestamp], pd.Timestamp]]`. Para cada corte de evaluación devuelve los cortes de entrenamiento, que son los que cumplen `c <= eval - gap_meses` (fin de mes).

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
def test_folds_spec():
    cortes = cortes_mensuales("2025-01-31", "2025-09-30")
    f = folds_temporales(cortes, [pd.Timestamp("2025-07-31"), pd.Timestamp("2025-08-31"), pd.Timestamp("2025-09-30")])
    assert f[0] == (cortes_mensuales("2025-01-31", "2025-04-30"), pd.Timestamp("2025-07-31"))
    assert f[2][0][-1] == pd.Timestamp("2025-06-30")
def test_sin_traslape():  # para todo fold: max(train) + 90 días <= eval
```

- [ ] **Paso 2:** ejecutar → FALLA. **Paso 3:** implementar. **Paso 4:** ejecutar → PASA.
- [ ] **Paso 5:** commit `feat: folds temporales con separacion`.

---

### Task 7 —: Economía y decisión

**Archivos:**
- Crear: `conecta/negocio.py`
- Probar: `tests/test_negocio.py`

**Interfaces:**
- Produce:
  - Constantes globales: `PRECIOS`, `COSTO_CONTACTO`, `EFECTIVIDAD`, `MESES_VALOR`.
  - `umbral(plan: str, costo=COSTO_CONTACTO, efectividad=EFECTIVIDAD) -> float`
  - `valor_esperado(p: pd.Series, plan: pd.Series, costo=..., efectividad=...) -> pd.Series` = `p·ef·12·precio − costo`
  - `decidir_contacto(p, plan, costo=..., efectividad=...) -> pd.Series[int]` = `(valor_esperado > 0).astype(int)`
  - `valor_realizado(contactar, churn_real, plan, costo=..., efectividad=...) -> float` = Σ sobre los contactados de `churn_real·ef·12·precio − costo`
  - `sensibilidad(p, plan, efectividades=(0.2, 0.4, 0.6)) -> pd.DataFrame` con columnas `efectividad, n_contactados, valor_esperado_total`.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
@pytest.mark.parametrize("plan,esperado", [("Basico",0.2180),("Estandar",0.1492),("Premium",0.1044),("Familiar",0.0870)])
def test_umbral(plan, esperado): assert umbral(plan) == pytest.approx(esperado, abs=1e-4)
def test_decidir_en_el_umbral_no_contacta():   # p == umbral exacto -> 0 (estricto)
def test_valor_realizado():
    # contactar=[1,1,0], churn=[1,0,1], plan Basico -> 0.4*12*23900 - 25000 - 25000 = 64720
    assert valor_realizado(pd.Series([1,1,0]), pd.Series([1,0,1]), pd.Series(["Basico"]*3)) == pytest.approx(64_720)
def test_plan_desconocido_falla():             # KeyError con mensaje que nombra el plan
```

- [ ] **Paso 2:** ejecutar → FALLA. **Paso 3:** implementar. **Paso 4:** ejecutar → PASA.
- [ ] **Paso 5:** commit `feat: economia y regla de contacto`.

---

### Task 8 —: Modelos, evaluación y MLflow (4 corridas)

**Archivos:**
- Crear: `conecta/modelos.py`
- Probar: agregar en `tests/test_validacion.py` una prueba de humo de `evaluar_corrida` sobre un panel sintético.

**Interfaces:**
- Consume: `construir_panel` (Tarea 5), `folds_temporales` (Tarea 6), `decidir_contacto` y `valor_realizado` (Tarea 7).
- Produce:
  - `VARIABLES_BASE: list[str]` (antigüedad, plan, atrasos, conteo de tickets). `VARIABLES_NO_ESTRUCTURADAS: list[str]` (todas las de `var_eventos` y `var_tickets`).
  - `crear_modelo(tipo: Literal["base", "gbm"], columnas: list[str]) -> sklearn.pipeline.Pipeline`. "base" = imputación + escalado + one-hot + `LogisticRegression`. "gbm" = LightGBM o `HistGradientBoostingClassifier` (lo eliges tú).
  - `evaluar_corrida(panel, folds, tipo, columnas, calibracion: str | None) -> dict` con, por fold y en promedio: `auc_pr, auc, brier, valor_realizado, valor_contactar_todos, valor_no_contactar (=0), n_contactados`.
  - `registrar_corrida(nombre: str, params: dict, metricas: dict, modelo) -> str` (run_id), con `mlflow.set_tracking_uri("file:./mlruns")`.

- [ ] **Paso 1:** escribir la prueba de humo: en un panel sintético de 3 cortes, `evaluar_corrida` devuelve las claves anteriores y `0 <= auc <= 1`.
- [ ] **Paso 2:** ejecutar → FALLA. **Paso 3:** implementar. **Paso 4:** ejecutar → PASA.
- [ ] **Paso 5:** en el notebook, correr y registrar:
  1. `base`: `crear_modelo("base", VARIABLES_BASE)`.
  2. `gbm_completo`: todas las variables.
  3. `gbm_sin_no_estructurados`: todas menos `VARIABLES_NO_ESTRUCTURADAS`.
  4. `gbm_historial_2023`: panel con cortes mensuales desde 2023-03-31 hasta 2025-09-30. Las variables de logs y del esquema B quedan NaN antes de 2025, con `fuente_disponible`. Se evalúa en los mismos 3 folds de 2025.
- [ ] **Paso 6:** imprimir `mlflow.search_runs()` con las métricas promedio. Elegir por `valor_realizado` promedio; con empate dentro de la dispersión entre folds, gana el más simple. Escribir la justificación en una celda de markdown. Agregar la curva de calibración de la corrida elegida y la importancia global (SHAP).
- [ ] **Paso 7:** commit `feat: modelos, evaluacion temporal y MLflow`.

---

### Task 9 —: Análisis del efecto de los llamados (spec §6.6)

**Archivos:**
- Modificar: `solucion.ipynb` (sección propia). Si hace falta, un parámetro `filtro_filas` en `evaluar_corrida`.

**Interfaces:**
- Consume: `evaluar_corrida` y `registrar_corrida` (Tarea 8).
- Produce: la decisión, escrita en el notebook, de entrenar el modelo final con corrección o sin ella.

- [ ] **Paso 1:** definir el diseño (decisión tuya). Por ejemplo: corrida A = la elegida en la Tarea 8; corrida B = la misma, excluyendo o reponderando las filas de clientes contactados dentro de la ventana `(corte, corte+90]`.
- [ ] **Paso 2:** registrar ambas en MLflow y compararlas con las mismas métricas y folds.
- [ ] **Paso 3:** decidir con números y escribir la lectura (qué cambia en el valor realizado y en la calibración).
- [ ] **Paso 4:** commit `feat: analisis del efecto de los llamados`.

---

### Task 10 —: Modelo final y `predicciones.csv`

**Archivos:**
- Modificar: `conecta/modelos.py` (agregar `validar_predicciones`)
- Probar: `tests/test_predicciones.py`
- Crear: `predicciones.csv`

**Interfaces:**
- Produce: `validar_predicciones(df: pd.DataFrame, ids_esperados: set[int]) -> None`, que lanza `ValueError` con un mensaje específico.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
def test_validar_ok()
@pytest.mark.parametrize("caso", ["id_faltante","id_duplicado","prob_nan","prob_fuera_rango","contactar_2","columnas_extra"])
def test_validar_falla(caso): ...  # ValueError cuyo mensaje nombra el problema
```

- [ ] **Paso 2:** ejecutar → FALLA. **Paso 3:** implementar. **Paso 4:** ejecutar → PASA.
- [ ] **Paso 5:** en el notebook:
  - Reentrenar la configuración elegida con todos los cortes de ene a sep.
  - Calibrar con los cortes más recientes (método y cortes a tu criterio, spec §9).
  - Puntuar la matriz al 2025-12-31.
  - Aplicar `decidir_contacto`, llamar a `validar_predicciones` y escribir `predicciones.csv`.
  - Mostrar el valor esperado total, los contactados por plan y segmento, la tabla de `sensibilidad` y la nota sobre los tickets de "cancelar".
- [ ] **Paso 6:** commit `feat: modelo final y predicciones`.

---

### Task 11 —: Hallazgos

**Archivos:**
- Modificar: `solucion.ipynb` (sección "Hallazgos")

- [ ] **Paso 1:** recalcular con los datos limpios la evidencia del spec §6.7 y comparar con los valores preliminares:
  - Tasa de error por versión y mes.
  - Churn de sep: usuarios de la 5.2.0 contra el resto (esperado ≈ 28 % contra 10 %).
  - Churn por plataforma en jun y sep.
  - Tickets de "app_se_cierra" por mes.
  - Cobros duplicados por año y su cruce con los tickets de cobro doble (esperado 100 %).
  - Contactados: % que cancela y días entre el contacto y la baja (esperado: mediana de 11).
- [ ] **Paso 2:** un gráfico por hallazgo y una celda de markdown con evidencia, salvedades (el sesgo en el hallazgo de retención) y acción.
- [ ] **Paso 3:** commit `docs: hallazgos con evidencia`.

---

### Task 12 —: Producción, memo, bitácora y README

**Archivos:**
- Crear: `MEMO.md`, `BITACORA_IA.md`, `README.md`
- Modificar: `solucion.ipynb` (sección "Producción")

- [ ] **Paso 1:** sección "Producción" en el notebook, con el contenido del spec §6.8. Máximo media página.
- [ ] **Paso 2:** `MEMO.md`, una página y sin jerga. Qué hacer (a quién llamar y por qué ahora), impacto esperado en pesos (de la Tarea 10), los tres hallazgos con su acción y las limitaciones.
- [ ] **Paso 3:** `BITACORA_IA.md`. Los momentos listados en el spec §6.9, las correcciones de la Tarea 4 y las horas invertidas.
- [ ] **Paso 4:** `README.md`. Estructura, cómo ejecutar en Colab (subir el zip y correr todo), botón "Open in Colab" (`https://colab.research.google.com/github/<usuario>/<repo>/blob/main/solucion.ipynb`), cómo correr `pytest` y el enlace al dashboard si existe.
- [ ] **Paso 5:** commit `docs: produccion, memo, bitacora y readme`.

---

### Task 13 —: Corrida completa en Colab y publicación

- [ ] **Paso 1:** crear el repo público en GitHub y hacer push.
- [ ] **Paso 2:** abrir desde el botón del README en un runtime de Colab limpio, subir `datos_conecta.zip` y ejecutar "Ejecutar todo". Esperado: sin errores y `predicciones.csv` regenerado e idéntico al del repo (o con diferencias explicadas por la semilla).
- [ ] **Paso 3:** guardar el notebook con salidas y hacer commit y push `chore: notebook ejecutado en Colab`.
- [ ] **Paso 4:** comprobar que el repo no contiene `datos/`, el zip, `mlruns/` ni `docs/superpowers/spikes/`, y que el CSV de tickets no tiene textos.

---

### Task 14 — (bonus, solo si sobra tiempo; la escribe Claude): Dashboard Streamlit

**Archivos:**
- Crear: `dashboard/app.py`, `dashboard/requirements.txt`, `dashboard/clientes_dashboard.csv` (exportado por el notebook)
- Modificar: `solucion.ipynb` (celda que exporta)

**Interfaces:**
- Consume: `predicciones.csv`, más un CSV con las columnas `cliente_id, plan, segmento, plataforma, probabilidad, valor_esperado, contactar, factor_1, factor_2, factor_3` (los factores salen de los SHAP por cliente) y la función `negocio.valor_esperado`.

- [ ] **Paso 1:** celda del notebook que exporta `dashboard/clientes_dashboard.csv`, sin datos crudos ni personales (sin ciudad ni edad).
- [ ] **Paso 2:** `app.py` con cuatro vistas:
  - Resumen de la campaña.
  - Lista de a quién llamar, ordenada por valor esperado y con filtros por plan, segmento y plataforma.
  - Ficha de cliente con sus 3 factores.
  - Controles de costo y efectividad que recalculan la decisión usando `negocio.py`.
- [ ] **Paso 3:** probar localmente con `streamlit run dashboard/app.py`. Al cambiar la efectividad a 0,2, el número de contactados tiene que bajar.
- [ ] **Paso 4:** publicar en Streamlit Community Cloud, poner el enlace en el README y hacer commit `feat: dashboard streamlit`.

---

## Anexo: nombres en inglés (instrucción del candidato, 2026-11-20)

Los identificadores de código van en inglés. Las columnas de la fuente (`cliente_id`, `fecha_inicio`, …) y las de `predicciones.csv` (`cliente_id, probabilidad, contactar`) no cambian. La prosa, los comentarios y los docstrings van en español. Equivalencias con los nombres del plan:

| Plan | Código |
|---|---|
| módulos `datos, tickets, etiquetas, variables, validacion, negocio, modelos` | `data, tickets, labels, features, validation, business, models` |
| `Datos` (clientes, suscripciones, facturas, etiquetas, a_puntuar, eventos, tickets_raw, tickets) | `Data` (clients, subscriptions, invoices, labels, to_score, events, tickets_raw, tickets) |
| `cargar_datos, normalizar_ciudad, limpiar_edad, limpiar_facturas (es_cobro_duplicado), limpiar_eventos (fecha_local), limpiar` | `load_data, normalize_city, clean_age, clean_invoices (is_duplicate_charge), clean_events (local_date), clean` |
| `unificar_tickets, hash_texto` (columnas `fecha, tema_origen, texto, estado abierto/cerrado, fecha_resolucion, esquema`) | `unify_tickets, hash_text` (columnas `created_at, source_topic, text, status open/closed, resolved_at, schema`) |
| `cortes_mensuales, activos_en, construir_etiquetas` (`fecha_corte`) | `monthly_cutoffs, active_at, build_labels` (`cutoff`) |
| `TEMAS, regla_molesto, clasificar_textos, cargar_clasificacion` (`tema, conf_tema, p_amenaza, p_ironia, ira, molesto`) | `TOPICS, annoyed_rule, classify_texts, load_classification` (`topic, topic_conf, p_threat, p_irony, anger, annoyed`) |
| `var_cliente, var_suscripcion, var_facturas, var_eventos, var_tickets, var_contactos, construir_matriz, construir_panel` | `client_features, subscription_features, invoice_features, event_features, ticket_features, contact_features, build_matrix, build_panel` |
| `folds_temporales` | `temporal_folds` |
| `PRECIOS, COSTO_CONTACTO, EFECTIVIDAD, MESES_VALOR, umbral, valor_esperado, decidir_contacto, valor_realizado, sensibilidad` | `PRICES, CONTACT_COST, EFFECTIVENESS, VALUE_MONTHS, threshold, expected_value, decide_contact, realized_value, sensitivity` |
| `VARIABLES_BASE, VARIABLES_NO_ESTRUCTURADAS, crear_modelo, evaluar_corrida, registrar_corrida, validar_predicciones` | `BASE_FEATURES, UNSTRUCTURED_FEATURES, make_model, evaluate_run, log_run, validate_predictions` |
