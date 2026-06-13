/*
Migración operativa actual de JugueteríaBot.
Incluye proveedores, entradas multiproducto, precio compra/venta, ventas entregadas con ganancia, notificaciones internas y Mercado Pago.
Es idempotente; puede ejecutarse más de una vez.
*/
/* Corrección crítica: el carrito conversacional y metadatos de pago pueden superar 500 caracteres. */
IF EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID('MemoriaCliente')
      AND name = 'notas_cliente'
      AND max_length <> -1
)
BEGIN
    ALTER TABLE MemoriaCliente ALTER COLUMN notas_cliente NVARCHAR(MAX) NULL;
END;


IF COL_LENGTH('Juguete', 'precio_compra') IS NULL
    ALTER TABLE Juguete ADD precio_compra DECIMAL(18,2) NOT NULL CONSTRAINT DF_Juguete_precio_compra DEFAULT 0;

IF OBJECT_ID('Proveedor', 'U') IS NULL
BEGIN
    CREATE TABLE Proveedor (
        id_proveedor INT IDENTITY(1,1) PRIMARY KEY,
        nombre NVARCHAR(150) NOT NULL,
        telefono NVARCHAR(20) NULL,
        correo NVARCHAR(150) NULL,
        empresa NVARCHAR(150) NULL,
        notas NVARCHAR(MAX) NULL,
        activo BIT NOT NULL DEFAULT 1,
        fecha_registro DATETIME NOT NULL DEFAULT GETDATE()
    );
END;

IF OBJECT_ID('EntradaInventario', 'U') IS NULL
BEGIN
    CREATE TABLE EntradaInventario (
        id_entrada INT IDENTITY(1,1) PRIMARY KEY,
        id_proveedor INT NULL,
        fecha_entrada DATETIME NOT NULL DEFAULT GETDATE(),
        total_costo DECIMAL(18,2) NOT NULL DEFAULT 0,
        observaciones NVARCHAR(MAX) NULL,
        usuario_registro NVARCHAR(100) NULL,
        CONSTRAINT FK_EntradaInventario_Proveedor FOREIGN KEY (id_proveedor) REFERENCES Proveedor(id_proveedor)
    );
END;

IF OBJECT_ID('DetalleEntradaInventario', 'U') IS NULL
BEGIN
    CREATE TABLE DetalleEntradaInventario (
        id_detalle_entrada INT IDENTITY(1,1) PRIMARY KEY,
        id_entrada INT NOT NULL,
        id_juguete INT NOT NULL,
        cantidad INT NOT NULL,
        costo_unitario DECIMAL(18,2) NOT NULL DEFAULT 0,
        subtotal DECIMAL(18,2) NOT NULL DEFAULT 0,
        CONSTRAINT FK_DetalleEntrada_Entrada FOREIGN KEY (id_entrada) REFERENCES EntradaInventario(id_entrada),
        CONSTRAINT FK_DetalleEntrada_Juguete FOREIGN KEY (id_juguete) REFERENCES Juguete(id_juguete),
        CONSTRAINT CK_DetalleEntrada_Cantidad CHECK (cantidad > 0),
        CONSTRAINT CK_DetalleEntrada_Costo CHECK (costo_unitario >= 0)
    );
END;

IF OBJECT_ID('NotificacionSistema', 'U') IS NULL
BEGIN
    CREATE TABLE NotificacionSistema (
        id_notificacion INT IDENTITY(1,1) PRIMARY KEY,
        tipo NVARCHAR(50) NOT NULL,
        titulo NVARCHAR(150) NOT NULL,
        mensaje NVARCHAR(MAX) NOT NULL,
        leida BIT NOT NULL DEFAULT 0,
        fecha_creacion DATETIME NOT NULL DEFAULT GETDATE()
    );
END;

IF OBJECT_ID('PagoMercadoPago', 'U') IS NULL
BEGIN
    CREATE TABLE PagoMercadoPago (
        id_pago_mp INT IDENTITY(1,1) PRIMARY KEY,
        id_pedido INT NOT NULL,
        preference_id NVARCHAR(120) NULL,
        payment_id NVARCHAR(120) NULL,
        status NVARCHAR(50) NULL,
        status_detail NVARCHAR(120) NULL,
        init_point NVARCHAR(MAX) NULL,
        sandbox_init_point NVARCHAR(MAX) NULL,
        raw_json NVARCHAR(MAX) NULL,
        fecha_creacion DATETIME NOT NULL DEFAULT GETDATE(),
        fecha_actualizacion DATETIME NULL,
        CONSTRAINT FK_PagoMP_Pedido FOREIGN KEY (id_pedido) REFERENCES Pedido(id_pedido)
    );
END;

IF COL_LENGTH('DetallePedido', 'costo_unitario') IS NULL
    ALTER TABLE DetallePedido ADD costo_unitario DECIMAL(18,2) NOT NULL CONSTRAINT DF_DetallePedido_costo_unitario DEFAULT 0;

IF COL_LENGTH('Pedido', 'stock_descontado') IS NULL ALTER TABLE Pedido ADD stock_descontado BIT NOT NULL CONSTRAINT DF_Pedido_stock_descontado DEFAULT 0;
IF COL_LENGTH('Pedido', 'fecha_entregado') IS NULL ALTER TABLE Pedido ADD fecha_entregado DATETIME NULL;
IF COL_LENGTH('Pedido', 'observaciones') IS NULL ALTER TABLE Pedido ADD observaciones NVARCHAR(MAX) NULL;
IF COL_LENGTH('Pedido', 'estado_pago') IS NULL ALTER TABLE Pedido ADD estado_pago NVARCHAR(50) NULL;
IF COL_LENGTH('Pedido', 'mercadopago_preference_id') IS NULL ALTER TABLE Pedido ADD mercadopago_preference_id NVARCHAR(120) NULL;
IF COL_LENGTH('Pedido', 'mercadopago_init_point') IS NULL ALTER TABLE Pedido ADD mercadopago_init_point NVARCHAR(MAX) NULL;
IF COL_LENGTH('Pedido', 'costo_envio') IS NULL ALTER TABLE Pedido ADD costo_envio DECIMAL(18,2) NOT NULL CONSTRAINT DF_Pedido_costo_envio DEFAULT 0;
IF COL_LENGTH('Pedido', 'metodo_pago') IS NULL ALTER TABLE Pedido ADD metodo_pago NVARCHAR(50) NULL;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Pedido_Estado_FechaEntregado')
CREATE INDEX IX_Pedido_Estado_FechaEntregado ON Pedido(estado, fecha_entregado);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Juguete_Stock')
CREATE INDEX IX_Juguete_Stock ON Juguete(stock);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_PagoMercadoPago_Pedido')
CREATE INDEX IX_PagoMercadoPago_Pedido ON PagoMercadoPago(id_pedido, fecha_actualizacion);

/* =========================================================
   ACTUALIZACIÓN COMERCIAL: VENTAS MANUALES, CÓDIGOS,
   CORTES, USUARIOS, RESPALDOS Y CFDI
   ========================================================= */
IF COL_LENGTH('Juguete', 'codigo_barras') IS NULL
    ALTER TABLE Juguete ADD codigo_barras NVARCHAR(80) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Juguete_codigo_barras' AND object_id = OBJECT_ID('Juguete'))
BEGIN
    CREATE UNIQUE INDEX UX_Juguete_codigo_barras
    ON Juguete(codigo_barras)
    WHERE codigo_barras IS NOT NULL AND codigo_barras <> '';
END
GO
IF COL_LENGTH('Pedido', 'canal_venta') IS NULL
    ALTER TABLE Pedido ADD canal_venta NVARCHAR(50) NULL;
GO
IF COL_LENGTH('Pedido', 'id_expo') IS NULL
    ALTER TABLE Pedido ADD id_expo INT NULL;
GO
IF COL_LENGTH('Pedido', 'id_corte') IS NULL
    ALTER TABLE Pedido ADD id_corte INT NULL;
GO
IF OBJECT_ID('UsuarioPanel', 'U') IS NULL
BEGIN
    CREATE TABLE UsuarioPanel (
        id_usuario INT IDENTITY(1,1) PRIMARY KEY,
        usuario NVARCHAR(80) NOT NULL UNIQUE,
        password_hash NVARCHAR(128) NOT NULL,
        nombre NVARCHAR(150) NULL,
        rol NVARCHAR(30) NOT NULL,
        activo BIT NOT NULL DEFAULT 1,
        fecha_creacion DATETIME NOT NULL DEFAULT GETDATE(),
        ultimo_acceso DATETIME NULL
    );
END
GO
IF OBJECT_ID('CorteCaja', 'U') IS NULL
BEGIN
    CREATE TABLE CorteCaja (
        id_corte INT IDENTITY(1,1) PRIMARY KEY,
        fecha_apertura DATETIME NOT NULL DEFAULT GETDATE(),
        fecha_cierre DATETIME NULL,
        usuario_apertura NVARCHAR(100) NULL,
        usuario_cierre NVARCHAR(100) NULL,
        monto_inicial DECIMAL(18,2) NOT NULL DEFAULT 0,
        ventas_efectivo DECIMAL(18,2) NOT NULL DEFAULT 0,
        ventas_online DECIMAL(18,2) NOT NULL DEFAULT 0,
        ventas_total DECIMAL(18,2) NOT NULL DEFAULT 0,
        efectivo_esperado DECIMAL(18,2) NOT NULL DEFAULT 0,
        efectivo_contado DECIMAL(18,2) NULL,
        diferencia DECIMAL(18,2) NULL,
        observaciones NVARCHAR(MAX) NULL,
        estado NVARCHAR(20) NOT NULL DEFAULT 'Abierto'
    );
END
GO
IF OBJECT_ID('FacturaCFDI', 'U') IS NULL
BEGIN
    CREATE TABLE FacturaCFDI (
        id_factura INT IDENTITY(1,1) PRIMARY KEY,
        id_pedido INT NOT NULL,
        rfc NVARCHAR(13) NOT NULL,
        razon_social NVARCHAR(250) NOT NULL,
        regimen_fiscal NVARCHAR(10) NULL,
        uso_cfdi NVARCHAR(10) NULL,
        codigo_postal NVARCHAR(10) NULL,
        correo NVARCHAR(150) NULL,
        estado NVARCHAR(30) NOT NULL DEFAULT 'Solicitada',
        uuid NVARCHAR(80) NULL,
        notas NVARCHAR(MAX) NULL,
        fecha_solicitud DATETIME NOT NULL DEFAULT GETDATE(),
        fecha_timbrado DATETIME NULL,
        CONSTRAINT FK_FacturaCFDI_Pedido FOREIGN KEY (id_pedido) REFERENCES Pedido(id_pedido)
    );
END
GO

/* =========================================================
   ACTUALIZACIÓN: PROVEEDOR, FOTOS Y CÓDIGO DE BARRAS EN JUGUETES
   ========================================================= */
IF COL_LENGTH('Juguete', 'id_proveedor') IS NULL
BEGIN
    ALTER TABLE Juguete ADD id_proveedor INT NULL;
END;
GO

IF COL_LENGTH('Juguete', 'foto_url') IS NULL
BEGIN
    ALTER TABLE Juguete ADD foto_url NVARCHAR(MAX) NULL;
END;
GO

IF COL_LENGTH('Juguete', 'foto_local') IS NULL
BEGIN
    ALTER TABLE Juguete ADD foto_local NVARCHAR(MAX) NULL;
END;
GO

IF COL_LENGTH('Juguete', 'codigo_barras') IS NULL
BEGIN
    ALTER TABLE Juguete ADD codigo_barras NVARCHAR(80) NULL;
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Juguete_codigo_barras' AND object_id = OBJECT_ID('Juguete'))
BEGIN
    CREATE UNIQUE INDEX UX_Juguete_codigo_barras
    ON Juguete(codigo_barras)
    WHERE codigo_barras IS NOT NULL AND codigo_barras <> '';
END;
GO

IF OBJECT_ID('Proveedor', 'U') IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Juguete_Proveedor')
BEGIN
    ALTER TABLE Juguete
    ADD CONSTRAINT FK_Juguete_Proveedor FOREIGN KEY (id_proveedor)
    REFERENCES Proveedor(id_proveedor);
END;
GO

/* =========================================================
   ACTUALIZACIÓN IA: AGENTE PRINCIPAL OPENAI + LOGS
   También disponible por separado en MIGRACION_AGENTE_OPENAI.sql
   ========================================================= */
IF OBJECT_ID('ContextoCliente', 'U') IS NULL
BEGIN
    CREATE TABLE ContextoCliente (
        id_contexto INT IDENTITY(1,1) PRIMARY KEY,
        id_cliente INT NOT NULL,
        ultima_intencion NVARCHAR(80) NULL,
        ultima_categoria NVARCHAR(120) NULL,
        ultimo_termino NVARCHAR(250) NULL,
        ultimo_producto NVARCHAR(250) NULL,
        fecha_actualizacion DATETIME NOT NULL DEFAULT GETDATE(),
        CONSTRAINT FK_ContextoCliente_Cliente FOREIGN KEY (id_cliente) REFERENCES Cliente(id_cliente)
    );
END;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_ContextoCliente_id_cliente' AND object_id = OBJECT_ID('ContextoCliente'))
BEGIN
    CREATE UNIQUE INDEX UX_ContextoCliente_id_cliente ON ContextoCliente(id_cliente);
END;
GO
IF OBJECT_ID('LogClasificacionAI', 'U') IS NULL
BEGIN
    CREATE TABLE LogClasificacionAI (
        id_log_ai INT IDENTITY(1,1) PRIMARY KEY,
        id_cliente INT NULL,
        mensaje_original NVARCHAR(MAX) NOT NULL,
        analisis_reglas NVARCHAR(MAX) NULL,
        clasificacion_ai NVARCHAR(MAX) NULL,
        respuesta_final NVARCHAR(MAX) NULL,
        fuente_clasificacion NVARCHAR(80) NULL,
        fecha_creacion DATETIME NOT NULL DEFAULT GETDATE(),
        CONSTRAINT FK_LogClasificacionAI_Cliente FOREIGN KEY (id_cliente) REFERENCES Cliente(id_cliente)
    );
END;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_LogClasificacionAI_Cliente_Fecha' AND object_id = OBJECT_ID('LogClasificacionAI'))
BEGIN
    CREATE INDEX IX_LogClasificacionAI_Cliente_Fecha ON LogClasificacionAI(id_cliente, fecha_creacion DESC);
END;
GO
IF OBJECT_ID('LogConversacionAgente', 'U') IS NULL
BEGIN
    CREATE TABLE LogConversacionAgente (
        id_log_agente INT IDENTITY(1,1) PRIMARY KEY,
        id_cliente INT NULL,
        telefono NVARCHAR(30) NULL,
        mensaje_cliente NVARCHAR(MAX) NOT NULL,
        json_agente NVARCHAR(MAX) NULL,
        accion_final NVARCHAR(80) NULL,
        respuesta_bot NVARCHAR(MAX) NULL,
        proveedor_whatsapp NVARCHAR(30) NULL,
        modelo_openai NVARCHAR(80) NULL,
        fecha_creacion DATETIME NOT NULL DEFAULT GETDATE(),
        CONSTRAINT FK_LogConversacionAgente_Cliente FOREIGN KEY (id_cliente) REFERENCES Cliente(id_cliente)
    );
END;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_LogConversacionAgente_Cliente_Fecha' AND object_id = OBJECT_ID('LogConversacionAgente'))
BEGIN
    CREATE INDEX IX_LogConversacionAgente_Cliente_Fecha ON LogConversacionAgente(id_cliente, fecha_creacion DESC);
END;
GO
