# Memo: por qué se van los clientes de Conecta+ y qué hacer en enero

Para: Gerencia de Conecta+ · Fecha: 31 de diciembre de 2025 · Base: datos de clientes, facturación, soporte y uso de la app, 2023 a 2025

La mayor fuga de clientes de este trimestre la causa un error nuestro: la versión 5.2.0 de la app para Android se cierra al abrir. Arreglarla rinde más que cualquier campaña de llamadas.

## Qué hacer, en orden

1. **Arreglar o retirar ya la versión 5.2.0 de la app para Android.** Salió el 1 de septiembre y la mitad de lo que registra son cierres inesperados. Entre los clientes de Android, quienes la usan se van 2,5 veces más que quienes siguen en la versión anterior: 28 % contra 11 % en tres meses. Todos los reclamos del año por "la app se cierra" llegaron desde entonces. Hoy la usan 464 clientes activos, 6 de cada 10 de la lista de riesgo. Mientras siga así, en un solo trimestre se irán unos 80 clientes de más, que entre todos pagan unos 36 millones de pesos al año.
2. **Corregir los cobros dobles y devolver el dinero antes de que el cliente reclame.** Los cobros dobles existen: cada cliente que reclamó uno tenía de verdad una factura repetida, y los casos pasaron de 47 en 2023 a 428 en 2025. Tras reclamar, 1 de cada 4 clientes se va en tres meses, el doble de lo normal.
3. **Llamar antes y medir si sirve.** Hoy el equipo de retención llama cuando el cliente ya está cancelando, en sus últimas tres semanas, y el 98 % se va igual; esas llamadas no recuperan lo que cuestan. El modelo avisa con hasta 90 días de anticipación. Propongo un piloto en enero: de los 100 clientes de mayor riesgo, llamar a 50 y comparar durante 2 o 3 meses con los otros 50. Son 50 llamadas al mes, unos 1,25 millones de pesos, algo menos de los 1,5 millones que gasta hoy el equipo.

## La lista de enero

El modelo marca a 634 de los 1.556 clientes activos para contactar (archivo `predicciones.csv`). La lista favorece los planes caros, porque retener a un cliente Familiar vale 2,5 veces lo que retener a uno Básico. Deja fuera a 13 clientes que ya están en proceso de baja: el equipo los llamó en el último mes o pidieron cancelar.

Si la llamada convence al 40 % de quienes iban a irse, como supone el enunciado, la lista rinde unos 16 millones de pesos netos después de pagar otros 16 millones en llamadas. Todo depende de ese 40 %. Con un 20 %, la lista baja a 237 clientes y rinde unos 3 millones; con un 10 %, casi ningún cliente justifica la llamada. Por eso propongo el piloto antes de llamar a toda la lista.

La lista, cliente por cliente y con los motivos de su riesgo, se puede consultar y filtrar en el tablero: https://unfresh25.github.io/conecta-churn/. Ahí también se puede cambiar el 40 % y ver cómo cambia la lista.

## Qué tan confiable es

- El modelo sabe a quién mirar. En una prueba que simula su uso en julio, agosto y septiembre, los 100 clientes que marcó como más riesgosos cada mes, sin contar a los que ya estaban en proceso de baja, se fueron entre 1,6 y 2,2 veces más que el promedio (de 24 % a 36 %, contra 15 % a 17 %). No adivina quién se va; ordena el riesgo.
- En abril a junio de 2025, con menos clientes yéndose y menos datos de uso de la app, la lista apenas habría cubierto el costo de las llamadas. Cuánto rinde depende de cuántos clientes se estén yendo.
- No sabemos si una llamada temprana retiene a alguien, porque nunca se ha hecho. El piloto sirve para averiguarlo.
- Los datos de uso de la app empiezan en enero de 2025, y de cada cliente solo se guarda la última llamada de retención.
- Los tres hallazgos salen de observar los datos, sin experimentos. El de la versión 5.2.0 es el más sólido, porque coinciden la fecha, la plataforma y el tipo de error.

El detalle técnico está en `solucion.ipynb`.
