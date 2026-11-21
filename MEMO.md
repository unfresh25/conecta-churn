# Memo: por qué se van los clientes de Conecta+ y qué hacer en enero

Para: Gerencia de Conecta+ · Fecha: 31 de diciembre de 2025 · Base: datos de clientes, facturación, soporte y uso de la app, 2023 a 2025

La mayor fuga de clientes de este trimestre la causa un error nuestro: la versión 5.2.0 de la app para Android se cierra al abrir. Es lo primero que hay que arreglar, antes de cualquier campaña de llamadas.

## Qué hacer, en orden

1. Arreglar o retirar ya la versión 5.2.0 de la app para Android. Salió el 1 de septiembre y la mitad de lo que registra son cierres inesperados. Entre los clientes de Android, quienes la usan se van 2,5 veces más que quienes siguen en la versión anterior: 28 % contra 11 % en tres meses. Todos los reclamos del año por "la app se cierra" llegaron desde entonces. Hoy la usan 464 clientes activos, 6 de cada 10 de la lista de enero. Si no se corrige, en un solo trimestre se irán unos 80 clientes de más, que entre todos pagan unos 36 millones de pesos al año.
2. Corregir los cobros dobles y devolver el dinero antes de que el cliente reclame. Cada cliente que reclamó un cobro doble tenía de verdad una factura repetida, y los casos pasaron de 47 en 2023 a 428 en 2025. Después de reclamar, 1 de cada 4 se va en tres meses, el doble de lo normal.
3. Llamar antes y medir si sirve. Hoy el equipo de retención llama cuando el cliente ya está cancelando, en sus últimas tres semanas, y el 98 % se va igual, así que esas llamadas no recuperan lo que cuestan. El modelo avisa con hasta 90 días de anticipación. Propongo un piloto en enero: de los 100 clientes de mayor riesgo, llamar a 50 y comparar con los otros 50 durante 2 o 3 meses. Son 50 llamadas al mes, unos 1,25 millones de pesos, algo menos de los 1,5 millones que gasta hoy el equipo.

## La lista de enero

El modelo marca para contactar a 634 de los 1.556 clientes activos (archivo `predicciones.csv`). Aparecen más clientes de planes caros, porque retener a uno del plan Familiar vale 2,5 veces lo que retener a uno del Básico. Quedan fuera 13 clientes que ya están en proceso de baja: el equipo los llamó en el último mes o pidieron cancelar.

El enunciado supone que la llamada convence al 40 % de quienes iban a irse. Con ese supuesto, la lista deja unos 16 millones de pesos netos después de gastar otros 16 millones en llamadas. Ese 40 % es lo que más pesa: con un 20 %, la lista baja a 237 clientes y deja unos 3 millones, y con un 10 % casi ninguna llamada se justifica. Por eso propongo el piloto antes de llamar a todos.

En el tablero https://unfresh25.github.io/conecta-churn/ se puede revisar cada cliente de la lista con los motivos de su riesgo, y probar otros porcentajes de efectividad.

## Qué tan confiable es

- En una prueba que simula su uso en julio, agosto y septiembre, los 100 clientes que el modelo marcó como más riesgosos cada mes (sin contar a los que ya estaban en proceso de baja) se fueron entre 1,6 y 2,2 veces más que el promedio: de 24 % a 36 %, contra 15 % a 17 %. El modelo no acierta cliente por cliente, pero sí pone primero a los que más probablemente se van.
- En abril a junio de 2025, cuando se iban menos clientes y había menos datos de uso de la app, la lista apenas habría cubierto el costo de las llamadas. Lo que rinde depende de cuántos clientes se estén yendo.
- No sabemos si una llamada temprana retiene a alguien, porque nunca se ha hecho. Para eso es el piloto.
- Los datos de uso de la app empiezan en enero de 2025, y de cada cliente solo se guarda la última llamada de retención.
- Los tres hallazgos salen de observar los datos, sin experimentos. El de la versión 5.2.0 es el más sólido, porque coinciden la fecha, la plataforma y el tipo de error.

El detalle técnico está en `solucion.ipynb`.
