# Actualización: fotos, proveedor y lector de barras en juguetes

## Cambios aplicados

1. En el alta/edición de juguetes se agregó:
   - Proveedor asignado.
   - Código de barras con lector por cámara.
   - Captura manual de código.
   - Foto local del producto.
   - URL externa de foto.

2. En la base de datos se agregan columnas a `Juguete`:
   - `id_proveedor INT NULL`
   - `foto_url NVARCHAR(MAX) NULL`
   - `foto_local NVARCHAR(MAX) NULL`
   - `codigo_barras NVARCHAR(80) NULL`

3. Se mantiene índice único filtrado para evitar repetir código de barras.

4. El bot ahora puede:
   - Detectar peticiones como “imagen de Stitch”, “foto del oso”, “mándame foto”.
   - Enviar la imagen del producto si está disponible.
   - Indicar al cliente que puede pedir imagen antes de agregar al carrito.
   - Cuando recibe una imagen del cliente y coincide con productos del catálogo, también envía imágenes disponibles de los productos parecidos.

## Nota importante para WhatsApp

Para que Meta WhatsApp pueda enviar imágenes por URL, `PUBLIC_BASE_URL` en `.env` debe apuntar a una URL pública HTTPS.

Ejemplo:

```env
PUBLIC_BASE_URL=https://tu-dominio.com
```

En pruebas puede ser ngrok, pero en producción conviene dominio propio con HTTPS.

## Compatibilidad del lector

El lector de código de barras del alta de productos usa `BarcodeDetector`, disponible principalmente en Chrome/Edge modernos. Si el navegador no lo soporta, el sistema permite captura manual.
