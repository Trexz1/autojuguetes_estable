# Actualización: precios, pagos y ganancia

## Cambios operativos

- Juguete ahora maneja precio de compra y precio de venta.
- El sistema bloquea guardar productos si el precio de compra es mayor que el de venta.
- Las entradas multiproducto validan que el costo unitario no exceda el precio de venta del producto.
- Al registrar una entrada se actualiza el último precio de compra del juguete y se suma stock.
- Las ventas reales solo cuentan si el pedido está en estado Entregado.
- La ganancia se calcula por producto: `(precio_venta - costo_unitario) * cantidad`.
- El envío a domicilio se agrega como cargo fijo configurado por `ENVIO_DOMICILIO`.
- El bot pregunta método de pago antes de confirmar: efectivo o pago en línea.
- Si el cliente elige pago en línea, se genera link de Mercado Pago al confirmar el pedido.
- El panel `/panel/pagos` permite verificar links y estados recibidos por webhook.

## Variables nuevas

```env
ENVIO_DOMICILIO=30
```

## Base de datos

Ejecutar o dejar que el sistema inicialice:

```sql
MIGRACION_OPERATIVA_ACTUAL.sql
```

La migración es idempotente.
