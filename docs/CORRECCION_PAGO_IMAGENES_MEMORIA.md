# Corrección: pago, memoria conversacional e imágenes públicas

## Problemas detectados

1. El bot podía intentar buscar `Hola` como producto si la memoria del cliente quedaba en un estado cerrado o desfasado.
2. Al responder `efectivo` o `pago en línea`, si el estado no estaba exactamente en `EsperandoMetodoPago`, el mensaje podía caer al buscador de productos.
3. WhatsApp rechazaba imágenes con el error `Param image.link is not a valid URI` cuando la URL enviada no era absoluta o `PUBLIC_BASE_URL` no estaba configurado correctamente.
4. La vista de juguetes podía mostrar imagen rota cuando la ruta guardada no estaba normalizada.

## Correcciones aplicadas

- Se agregó limpieza de memoria cerrada cuando el cliente saluda.
- Se agregó prioridad absoluta para procesar método de pago cuando existe carrito, aunque el estado se haya desfasado.
- Se validan URLs absolutas antes de enviar imágenes a Meta.
- Se normalizan rutas de fotos para panel: URLs externas, `/static/...`, `static/...`, `productos/...` y nombres de archivo.
- Se evita llamar a Meta con una ruta inválida.

## Variables necesarias

Para que WhatsApp pueda enviar imágenes locales, configurar:

```env
PUBLIC_BASE_URL=https://tu-dominio-o-ngrok.ngrok-free.app
```

Para pago en línea sin Mercado Pago automático:

```env
PAYMENT_LINK_FALLBACK=https://tu-link-de-pago.com
```

Si usas Mercado Pago automático:

```env
MERCADOPAGO_ACCESS_TOKEN=PEGA_AQUI_TU_ACCESS_TOKEN
```
