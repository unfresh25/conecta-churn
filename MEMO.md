# Memo: por qué se van los clientes de Conecta+ y qué hacer en enero

**Para:** Gerencia de Conecta+ · **Fecha:** 31 de diciembre de 2025 · **Base:** datos de clientes, facturación, soporte y uso de la app de 2023 a 2025

## En una frase

La mayor fuga de clientes de este trimestre la causa un error de la empresa: la versión 5.2.0 de la app para Android se cierra al abrir. Arreglarla rinde más que cualquier campaña de llamadas.

## Qué hacer, en orden

1. **Arreglar o retirar ya la versión 5.2.0 de la app (Android).** Desde que salió, el 1 de septiembre, la mitad de lo que registra son cierres inesperados. Entre los clientes de Android, quienes la usan se van 2,5 veces más que quienes siguen en la versión anterior (28 % contra 11 % en tres meses), y todos los reclamos de "la app se cierra" del año llegaron desde entonces. Hoy la usan 464 clientes activos, que son 6 de cada 10 de la lista de riesgo. Cada trimestre así se van unos 80 clientes de más, equivalentes a unos **36 millones de pesos de facturación anual**.
2. **Corregir los cobros dobles y devolver el dinero antes de que el cliente reclame.** No son percepción: todos los clientes que reclamaron un cobro doble tenían de verdad una factura repetida, y los casos crecieron de 47 en 2023 a 428 en 2025. Después de reclamar se va 1 de cada 4 clientes en tres meses, el doble de lo normal.
3. **Cambiar el momento de las llamadas de retención y probar antes de escalar.** Hoy el equipo llama cuando el cliente ya está cancelando, en sus últimas tres semanas: el 98 % se va igual. Esas llamadas no recuperan lo que cuestan. Proponemos llamar con anticipación usando la lista del modelo, que avisa con hasta 90 días. Empezaríamos con un **piloto en enero**: de los 100 clientes de mayor riesgo, llamar a 50 y comparar con los otros 50 durante 2 o 3 meses. Cuesta lo mismo que el equipo gasta hoy, unos 1,3 millones al mes.

## La lista de enero

El modelo marca a **634 de los 1.556 clientes activos** para contactar (archivo `predicciones.csv`). Se prioriza a los planes caros, porque retener a un cliente Familiar vale 2,5 veces lo que retener a uno Básico. Quedan fuera los 13 clientes que el equipo ya está atendiendo porque pidieron la baja.

Si se cumple el supuesto del enunciado (que la llamada convence al 40 % de quienes iban a irse), la lista rinde unos **16 millones de pesos netos**, después de pagar unos 16 millones en llamadas. Ese supuesto lo decide todo: si la llamada convence al 20 %, la lista se reduce a 237 clientes y rinde unos 3 millones; si convence al 10 %, casi nadie justifica la llamada. Por eso recomendamos el piloto antes de llamar a toda la lista.

## Qué tan confiable es

- El modelo identifica bien a quién mirar. En una prueba que simula su uso en julio, agosto y septiembre, sus primeros 100 clientes de cada mes se fueron entre 2 y 2,7 veces más que el promedio (30 % a 44 %, contra 15 % a 17 %). Aun así, no adivina quién se va: concentra el riesgo, nada más.
- Lo que no se sabe es si una llamada temprana retiene a alguien, porque nunca se ha hecho. El piloto existe para responder eso.
- Los datos de uso de la app solo existen desde enero de 2025, y de cada cliente solo se guarda la última llamada de retención.
- Los tres hallazgos vienen de observar datos, no de experimentos. El de la versión 5.2.0 es el más sólido: coinciden la fecha, la plataforma y el tipo de error.

El detalle técnico está en `solucion.ipynb`.
