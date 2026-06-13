# Actualización operativa: proveedores, entradas, ventas, PWA y Mercado Pago

## Módulos añadidos

- Proveedores: alta, edición, desactivación, validación de teléfono mexicano y correo.
- Entradas multiproducto: se elige proveedor, varios productos, cantidad y costo unitario. Al guardar, suma stock.
- Ventas: solo cuenta pedidos con estado `Entregado`; incluye gráfica y tickets imprimibles.
- Productos bajos en stock: dashboard muestra listado accionable con productos por debajo del umbral `STOCK_BAJO_UMBRAL`.
- Modo app Android: se añadió PWA con `manifest.webmanifest` y `service-worker.js`. Desde Chrome Android se instala con “Agregar a pantalla principal”. Para APK real se puede empaquetar como TWA con Bubblewrap cuando exista dominio HTTPS estable.
- Mercado Pago: generación de preferencias Checkout Pro por pedido y webhook básico para actualizar estado de pago.

## Variables nuevas

```env
MERCADOPAGO_ACCESS_TOKEN=PEGA_AQUI_TU_ACCESS_TOKEN
MERCADOPAGO_PUBLIC_KEY=APP_USR_TU_PUBLIC_KEY
PUBLIC_BASE_URL=https://tu-dominio-o-ngrok.ngrok-free.app
STOCK_BAJO_UMBRAL=3
```

## Reglas de venta

Una venta se suma únicamente cuando el pedido se marca como `Entregado`. El stock se descuenta en ese mismo momento, no antes.

## Ticket

Los tickets solo se imprimen desde pedidos entregados: `/panel/pedidos/ticket/{id_pedido}`.
