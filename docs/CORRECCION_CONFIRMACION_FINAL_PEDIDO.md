# Corrección: confirmación final obligatoria antes de crear pedido

## Problema detectado
El flujo podía registrar el pedido al seleccionar `efectivo` o `pago en línea`, sin esperar una confirmación final explícita.

También se detectó que frases como `ya es todo` no cerraban correctamente el carrito y podían caer al buscador de productos.

## Cambios aplicados

- `es_confirmacion_pedido()` ahora es estricta.
  - Ya no acepta solo `sí`, `ok`, `adelante` o `procede`.
  - Para crear pedido se requiere una frase final como `confirmar pedido`.

- `es_cancelacion_pedido()` ya no toma `no` como cancelación global.
  - Esto evita que `no` dentro de `EsperandoMasProductos` cancele el pedido.

- `es_no_agregar_otro()` ahora reconoce:
  - `ya es todo`
  - `ya sería todo`
  - `con eso`
  - `solo eso`
  - `finalizar compra`

- `flujo_pago_directo_desde_memoria()` solo actúa si el estado exacto es `EsperandoMetodoPago`.

- Al elegir método de pago, el estado pasa a `CompraListaParaConfirmacion` y se muestra resumen.

- El pedido solo se crea en `CompraListaParaConfirmacion` cuando el cliente responde exactamente con confirmación final.

## Flujo esperado

1. Producto
2. Confirmación de producto
3. Cantidad
4. Carrito
5. Preguntar si quiere agregar más
6. Entrega
7. Dirección
8. Referencia
9. Método de pago
10. Resumen final
11. Cliente responde: `confirmar pedido`
12. Se crea el pedido

