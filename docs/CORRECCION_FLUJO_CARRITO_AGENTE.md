# Corrección de flujo conversacional del carrito

Se aplicaron correcciones al motor conversacional para que el agente OpenAI no salte pasos críticos del pedido.

## Cambios principales

- Se normaliza el texto entrante del cliente a minúsculas y sin acentos antes de analizarlo.
- El flujo ya no brinca la pregunta de agregar más productos.
- Cuando el cliente envía producto + cantidad + entrega en un solo mensaje, el producto se agrega al carrito y luego se pregunta si desea agregar otro producto.
- En estados críticos como confirmación de producto, cantidad, dirección, referencia y pago, el bot redirige al cliente sin perder contexto.
- Si el cliente pregunta cómo funciona, el bot explica el formato correcto para continuar según el estado actual.
- Se conserva el `id_juguete` al guardar dirección para evitar que el pedido quede sin producto.
- El carrito se conserva dentro de `notas_cliente` con `CARRITO_JSON`.

## Flujo corregido

1. Cliente elige producto.
2. Bot confirma producto.
3. Cliente indica cantidad.
4. Bot agrega al carrito.
5. Bot pregunta si desea agregar más productos.
6. Si responde no, continúa a entrega.
7. Luego dirección, referencia, método de pago y cierre.
