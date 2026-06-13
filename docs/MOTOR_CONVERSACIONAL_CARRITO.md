# Motor conversacional y carrito

Esta actualización usa `MemoriaCliente` como motor de estado conversacional.

Estados principales:

- `CompraPendiente`: el cliente está eligiendo producto.
- `EsperandoCantidad`: ya hay producto detectado y falta cantidad.
- `EsperandoMasProductos`: el producto ya fue agregado al carrito y se pregunta si desea agregar otro.
- `EsperandoDireccion`: falta dirección para entrega a domicilio.
- `EsperandoReferencia`: falta referencia visual de entrega.
- `CompraListaParaConfirmacion`: el carrito tiene método de entrega y está listo para confirmar.
- `PedidoConfirmado`: el pedido ya se guardó.
- `CompraCancelada`: el cliente canceló el flujo.

## Regla de negocio

El stock no se descuenta al confirmar el pedido. El stock se descuenta únicamente cuando el panel marca el pedido como `Entregado`.

## OpenAI

OpenAI solo interpreta mensajes ambiguos. No decide precios, stock ni inventario. Todo precio, stock y existencia se consulta desde SQL Server.

## Carrito

El carrito se guarda dentro de `MemoriaCliente.notas_cliente` como JSON con el prefijo `CARRITO_JSON=` para evitar romper instalaciones existentes.
