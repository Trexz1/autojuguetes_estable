# Corrección de pago, carrito y fotos de productos

## Problema corregido

El bot perdía el carrito cuando el cliente elegía `efectivo` o `pago en línea` porque `notas_cliente` mezclaba el JSON del carrito con otros metadatos, por ejemplo:

```text
CARRITO_JSON=[...]; PAGO_METODO=Efectivo
```

La lectura anterior intentaba convertir todo lo posterior a `CARRITO_JSON=` como JSON. Al encontrar `; PAGO_METODO=...`, fallaba y el sistema interpretaba el carrito como vacío.

## Solución aplicada

- El parser del carrito ahora usa `json.JSONDecoder().raw_decode()` para leer solo el arreglo JSON válido.
- El estado `EsperandoMetodoPago` ahora pasa correctamente a `CompraListaParaConfirmacion`.
- Al elegir método de pago, el pedido se registra automáticamente.
- Si el método es `Pago en línea`, el sistema genera link con Mercado Pago si existe `MERCADOPAGO_ACCESS_TOKEN`.
- Si no hay token de Mercado Pago, usa `PAYMENT_LINK_FALLBACK` como link fijo de respaldo.
- Si el método es `Efectivo`, confirma el pedido como pago pendiente en efectivo.

## Cambio de base de datos necesario

Ejecutar `MIGRACION_OPERATIVA_ACTUAL.sql`. Incluye:

```sql
ALTER TABLE MemoriaCliente ALTER COLUMN notas_cliente NVARCHAR(MAX) NULL;
```

Esto evita que el carrito se corte cuando tenga varios productos.

## Fotos de productos

Las fotos locales ahora se sirven desde `RUNTIME_DIR/static/productos`, no desde el directorio temporal de PyInstaller. Esto corrige el caso donde el panel mostraba que sí había imagen pero el navegador no podía cargarla.

Para WhatsApp, las imágenes requieren:

```env
PUBLIC_BASE_URL=https://tu-dominio-publico-o-ngrok.ngrok-free.app
```

Sin una URL pública HTTPS, el panel puede ver la imagen local, pero WhatsApp no podrá descargarla.
