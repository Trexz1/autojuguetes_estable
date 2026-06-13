/*
Actualización: Agente principal OpenAI + JSON estructurado + logs.
Ejecutar sobre la base JugueteriaBot. Es idempotente.
*/

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
