
-- =============================================
-- PROYECTO: ORDENES-DOCKER
-- BASE DE DATOS: OrdenesDB
-- MOTOR: SQL SERVER 2022
-- =============================================

-- 1. Crear la base de datos si no existe
IF DB_ID(N'OrdenesDB') IS NULL
BEGIN
    EXEC(N'CREATE DATABASE OrdenesDB');
END;
GO

USE OrdenesDB;
GO

-- 2. Crear tabla de ordenes
IF OBJECT_ID(N'dbo.ordenes', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ordenes (
        id INT IDENTITY(1,1) PRIMARY KEY,
        cliente NVARCHAR(150) NOT NULL,
        fecha DATE NOT NULL DEFAULT (CONVERT(DATE, GETDATE())),
        estado NVARCHAR(20) NOT NULL
            DEFAULT 'Pendiente',
        total DECIMAL(12,2) NOT NULL DEFAULT 0,

        CONSTRAINT CK_ordenes_estado
        CHECK (estado IN ('Pendiente', 'Pagada', 'Anulada')),

        CONSTRAINT CK_ordenes_total
        CHECK (total >= 0)
    );
END;
GO

-- 3. Crear tabla de detalles
IF OBJECT_ID(N'dbo.orden_detalle', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.orden_detalle (
        id INT IDENTITY(1,1) PRIMARY KEY,
        orden_id INT NOT NULL,
        producto NVARCHAR(150) NOT NULL,
        cantidad INT NOT NULL,
        precio_unitario DECIMAL(12,2) NOT NULL,
        subtotal DECIMAL(12,2) NOT NULL,

        CONSTRAINT FK_detalle_orden
        FOREIGN KEY (orden_id)
        REFERENCES dbo.ordenes(id)
        ON DELETE CASCADE,

        CONSTRAINT CK_detalle_cantidad
        CHECK (cantidad > 0),

        CONSTRAINT CK_detalle_precio
        CHECK (precio_unitario >= 0),

        CONSTRAINT CK_detalle_subtotal
        CHECK (subtotal >= 0)
    );
END;
GO

-- 4. Insertar cinco ordenes de prueba
-- Cada orden tendrá dos detalles.

IF NOT EXISTS (SELECT 1 FROM dbo.ordenes)
BEGIN
    BEGIN TRANSACTION;

    SET IDENTITY_INSERT dbo.ordenes ON;

    INSERT INTO dbo.ordenes
        (id, cliente, fecha, estado, total)
    VALUES
        (1, 'Juan Perez', '2026-11-10', 'Pagada', 900.00),
        (2, 'Maria Lopez', '2026-11-11', 'Pendiente', 610.00),
        (3, 'Carlos Martinez', '2026-11-12', 'Pagada', 1550.00),
        (4, 'Ana Garcia', '2026-11-13', 'Pendiente', 850.00),
        (5, 'Pedro Hernandez', '2026-11-14', 'Anulada', 1200.00);

    SET IDENTITY_INSERT dbo.ordenes OFF;

    SET IDENTITY_INSERT dbo.orden_detalle ON;

    INSERT INTO dbo.orden_detalle
        (id, orden_id, producto, cantidad, precio_unitario, subtotal)
    VALUES
        (1, 1, 'Teclado', 1, 500.00, 500.00),
        (2, 1, 'Mouse', 2, 200.00, 400.00),

        (3, 2, 'Monitor', 3, 150.00, 450.00),
        (4, 2, 'Cable HDMI', 2, 80.00, 160.00),

        (5, 3, 'Laptop', 1, 1200.00, 1200.00),
        (6, 3, 'Audifonos', 1, 350.00, 350.00),

        (7, 4, 'Memoria USB', 5, 50.00, 250.00),
        (8, 4, 'Disco duro', 2, 300.00, 600.00),

        (9, 5, 'Impresora', 2, 450.00, 900.00),
        (10, 5, 'Tinta', 4, 75.00, 300.00);

    SET IDENTITY_INSERT dbo.orden_detalle OFF;

    COMMIT TRANSACTION;
END;
GO

-- 5. Consultar las ordenes
SELECT * FROM dbo.ordenes;
GO

-- 6. Consultar los detalles
SELECT * FROM dbo.orden_detalle;
GO

-- 7. Verificar los totales de cada orden
SELECT
    o.id,
    o.cliente,
    o.total AS total_guardado,
    SUM(d.subtotal) AS total_calculado
FROM dbo.ordenes o
INNER JOIN dbo.orden_detalle d
    ON o.id = d.orden_id
GROUP BY o.id, o.cliente, o.total
ORDER BY o.id;
GO
