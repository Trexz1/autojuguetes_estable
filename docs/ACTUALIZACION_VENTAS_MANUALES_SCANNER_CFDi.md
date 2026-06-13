# Actualización comercial: ventas manuales, scanner, cortes, usuarios, respaldo y CFDI

## Módulos agregados

### 1. Ventas manuales / expos
Ruta: `/panel/ventas/manual`

Permite vender sin pasar por el bot de WhatsApp. Funciona para mostrador, expo o domicilio manual. Al confirmar:

- crea un `Pedido` en estado `Entregado`;
- crea registros en `DetallePedido`;
- descuenta stock inmediatamente;
- genera ticket imprimible;
- permite seleccionar método de pago.

### 2. Código de barras en productos
Se agregó el campo `codigo_barras` en productos.

Validaciones:

- puede capturarse manualmente al crear/editar producto;
- no permite repetir códigos;
- se crea índice único filtrado en SQL Server.

### 3. API de búsqueda por código
Rutas:

- `GET /api/productos/codigo/{codigo}`
- `GET /api/productos/buscar?q=texto`

Estas rutas alimentan la venta manual y el scanner móvil.

### 4. Scanner móvil
La pantalla `/panel/ventas/manual` incluye modo teléfono:

- abre cámara;
- detecta código con `BarcodeDetector` si el navegador lo soporta;
- agrega el producto automáticamente;
- si escaneas varias veces el mismo producto, aumenta la cantidad.

Nota técnica: el acceso a cámara requiere HTTPS o localhost. En producción debe usarse dominio con SSL.

### 5. Cortes de caja
Ruta: `/panel/cortes`

Incluye:

- ventas del día;
- separación efectivo / pagos no efectivo;
- fondo inicial;
- efectivo contado;
- diferencia;
- historial de cortes.

### 6. Usuarios y roles
Ruta: `/panel/usuarios`

Roles:

- `admin`: acceso completo;
- `vendedor`: venta manual y pedidos;
- `caja`: ventas y cortes;
- `pedidos`: gestión de pedidos del bot;
- `lectura`: solo lectura.

Los usuarios comerciales se guardan en `UsuarioPanel`. Los usuarios `.env` anteriores siguen funcionando como respaldo.

### 7. Respaldo y restauración
Ruta: `/panel/respaldo`

Permite crear `.bak` de SQL Server desde la interfaz y restaurar respaldos existentes dentro de la carpeta `backups`.

La restauración requiere permisos suficientes del usuario de SQL Server y cierra conexiones activas de la base.

### 8. CFDI
Ruta: `/panel/cfdi`

Se agregó interfaz para capturar solicitudes de CFDI relacionadas con ventas entregadas.

Importante: este módulo guarda la solicitud administrativa. No timbra ante SAT. Para timbrado real se requiere integrar un PAC con credenciales fiscales.

## Migración SQL
El arranque ejecuta migración idempotente automáticamente desde `main.py`. También se dejó el bloque en:

`MIGRACION_OPERATIVA_ACTUAL.sql`

## Pruebas realizadas

- Compilación Python de `main.py` con `python -m py_compile main.py`.
- Verificación estática de rutas nuevas.
- Limpieza de cachés antes de empaquetar.

No se ejecutó prueba real contra SQL Server porque el entorno de empaquetado no incluye ODBC Driver/pyodbc ni acceso a la instancia local del cliente.
