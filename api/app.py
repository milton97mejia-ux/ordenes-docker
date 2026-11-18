
import os
from decimal import Decimal, InvalidOperation

import pyodbc
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ESTADOS_VALIDOS = ["Pendiente", "Pagada", "Anulada"]


# ==========================================
# CONEXION CON SQL SERVER
# ==========================================

def get_db_connection():
    server = os.getenv("DB_HOST", "db")
    port = os.getenv("DB_PORT", "1433")
    database = os.getenv("DB_NAME", "OrdenesDB")
    username = os.getenv("DB_USER", "sa")
    password = os.getenv("DB_PASSWORD")

    if not password:
        raise RuntimeError("No se ha configurado DB_PASSWORD")

    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=5;"
    )

    return pyodbc.connect(connection_string)


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def convertir_fila(cursor, fila):
    columnas = [columna[0] for columna in cursor.description]
    resultado = {}

    for nombre, valor in zip(columnas, fila):
        if isinstance(valor, Decimal):
            valor = float(valor)
        elif hasattr(valor, "isoformat"):
            valor = valor.isoformat()

        resultado[nombre] = valor

    return resultado


def recalcular_total(conexion, orden_id):
    cursor = conexion.cursor()

    cursor.execute("""
        UPDATE dbo.ordenes
        SET total = COALESCE(
            (SELECT SUM(subtotal)
             FROM dbo.orden_detalle
             WHERE orden_id = ?), 0
        )
        WHERE id = ?
    """, (orden_id, orden_id))

    cursor.close()


def error_servidor(error):
    app.logger.exception("Error interno de la API")
    return jsonify({
        "error": "Error interno del servidor"
    }), 500


# ==========================================
# RUTA PRINCIPAL
# ==========================================

@app.route("/", methods=["GET"])
def inicio():
    return jsonify({
        "mensaje": "API de Ordenes funcionando",
        "proyecto": "ordenes-docker",
        "framework": "Flask"
    }), 200


# ==========================================
# ESTADO DE LA API Y BASE DE DATOS
# ==========================================

@app.route("/health", methods=["GET"])
def health():
    conexion = None

    try:
        conexion = get_db_connection()
        cursor = conexion.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()

        return jsonify({
            "status": "healthy",
            "database": "connected"
        }), 200

    except Exception:
        app.logger.exception("Error de conexion")
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected"
        }), 503

    finally:
        if conexion:
            conexion.close()


# ==========================================
# CRUD DE ORDENES
# ==========================================

# CONSULTAR TODAS LAS ORDENES
@app.route("/api/ordenes", methods=["GET"])
def listar_ordenes():
    conexion = None

    try:
        conexion = get_db_connection()
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT id, cliente, fecha, estado, total
            FROM dbo.ordenes
            ORDER BY id
        """)

        ordenes = [
            convertir_fila(cursor, fila)
            for fila in cursor.fetchall()
        ]

        cursor.close()
        return jsonify(ordenes), 200

    except Exception as error:
        return error_servidor(error)

    finally:
        if conexion:
            conexion.close()


# CREAR UNA ORDEN
@app.route("/api/ordenes", methods=["POST"])
def crear_orden():
    conexion = None

    try:
        datos = request.get_json(silent=True) or {}

        cliente = datos.get("cliente")
        estado = datos.get("estado", "Pendiente")

        if not isinstance(cliente, str) or not cliente.strip():
            return jsonify({"error": "El cliente es obligatorio"}), 400

        if estado not in ESTADOS_VALIDOS:
            return jsonify({"error": "Estado no valido"}), 400

        conexion = get_db_connection()
        cursor = conexion.cursor()

        if datos.get("fecha"):
            cursor.execute("""
                INSERT INTO dbo.ordenes (cliente, fecha, estado)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?)
            """, (cliente.strip(), datos["fecha"], estado))
        else:
            cursor.execute("""
                INSERT INTO dbo.ordenes (cliente, estado)
                OUTPUT INSERTED.id
                VALUES (?, ?)
            """, (cliente.strip(), estado))

        nuevo_id = cursor.fetchone()[0]
        conexion.commit()
        cursor.close()

        return jsonify({
            "mensaje": "Orden creada correctamente",
            "id": nuevo_id
        }), 201

    except Exception as error:
        if conexion:
            conexion.rollback()
        return error_servidor(error)

    finally:
        if conexion:
            conexion.close()


# CONSULTAR UNA ORDEN
@app.route("/api/ordenes/<int:orden_id>", methods=["GET"])
def obtener_orden(orden_id):
    conexion = None

    try:
        conexion = get_db_connection()
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT id, cliente, fecha, estado, total
            FROM dbo.ordenes
            WHERE id = ?
        """, (orden_id,))

        fila = cursor.fetchone()

        if not fila:
            return jsonify({"error": "Orden no encontrada"}), 404

        orden = convertir_fila(cursor, fila)

        cursor.execute("""
            SELECT id, orden_id, producto, cantidad,
                   precio_unitario, subtotal
            FROM dbo.orden_detalle
            WHERE orden_id = ?
            ORDER BY id
        """, (orden_id,))

        orden["detalles"] = [
            convertir_fila(cursor, fila)
            for fila in cursor.fetchall()
        ]

        cursor.close()

        return jsonify(orden), 200

    except Exception as error:
        return error_servidor(error)

    finally:
        if conexion:
            conexion.close()


# ACTUALIZAR UNA ORDEN
@app.route("/api/ordenes/<int:orden_id>", methods=["PUT"])
def actualizar_orden(orden_id):
    conexion = None

    try:
        datos = request.get_json(silent=True) or {}

        campos = []
        valores = []

        if "cliente" in datos:
            cliente = datos["cliente"]

            if not isinstance(cliente, str) or not cliente.strip():
                return jsonify({"error": "Cliente no valido"}), 400

            campos.append("cliente = ?")
            valores.append(cliente.strip())

        if "fecha" in datos:
            campos.append("fecha = ?")
            valores.append(datos["fecha"])

        if "estado" in datos:
            if datos["estado"] not in ESTADOS_VALIDOS:
                return jsonify({"error": "Estado no valido"}), 400

            campos.append("estado = ?")
            valores.append(datos["estado"])

        if not campos:
            return jsonify({"error": "No hay datos para actualizar"}), 400

        conexion = get_db_connection()
        cursor = conexion.cursor()

        valores.append(orden_id)

        cursor.execute(
            "UPDATE dbo.ordenes SET "
            + ", ".join(campos)
            + " WHERE id = ?",
            valores
        )

        if cursor.rowcount == 0:
            conexion.rollback()
            return jsonify({"error": "Orden no encontrada"}), 404

        conexion.commit()
        cursor.close()

        return jsonify({
            "mensaje": "Orden actualizada correctamente"
        }), 200

    except Exception as error:
        if conexion:
            conexion.rollback()
        return error_servidor(error)

    finally:
        if conexion:
            conexion.close()


# ELIMINAR UNA ORDEN
@app.route("/api/ordenes/<int:orden_id>", methods=["DELETE"])
def eliminar_orden(orden_id):
    conexion = None

    try:
        conexion = get_db_connection()
        cursor = conexion.cursor()

        cursor.execute("""
            DELETE FROM dbo.ordenes
            WHERE id = ?
        """, (orden_id,))

        if cursor.rowcount == 0:
            conexion.rollback()
            return jsonify({"error": "Orden no encontrada"}), 404

        conexion.commit()
        cursor.close()

        return jsonify({
            "mensaje": "Orden eliminada correctamente"
        }), 200

    except Exception as error:
        if conexion:
            conexion.rollback()
        return error_servidor(error)

    finally:
        if conexion:
            conexion.close()


# ==========================================
# CRUD DE DETALLES DE ORDENES
# ==========================================

# CONSULTAR DETALLES DE UNA ORDEN
@app.route("/api/ordenes/<int:orden_id>/detalles", methods=["GET"])
def listar_detalles(orden_id):
    conexion = None

    try:
        conexion = get_db_connection()
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT id, orden_id, producto, cantidad,
                   precio_unitario, subtotal
            FROM dbo.orden_detalle
            WHERE orden_id = ?
            ORDER BY id
        """, (orden_id,))

        detalles = [
            convertir_fila(cursor, fila)
            for fila in cursor.fetchall()
        ]

        cursor.close()
        return jsonify(detalles), 200

    except Exception as error:
        return error_servidor(error)

    finally:
        if conexion:
            conexion.close()


# AGREGAR UN DETALLE
@app.route("/api/ordenes/<int:orden_id>/detalles", methods=["POST"])
def crear_detalle(orden_id):
    conexion = None

    try:
        datos = request.get_json(silent=True) or {}

        producto = datos.get("producto")
        cantidad = datos.get("cantidad")
        precio = datos.get("precio_unitario")

        if not isinstance(producto, str) or not producto.strip():
            return jsonify({"error": "Producto obligatorio"}), 400

        if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad <= 0:
            return jsonify({"error": "Cantidad debe ser un entero positivo"}), 400

        try:
            precio = Decimal(str(precio))
            if not precio.is_finite() or precio < 0:
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            return jsonify({"error": "Precio no valido"}), 400

        subtotal = (precio * cantidad).quantize(Decimal("0.01"))

        conexion = get_db_connection()
        cursor = conexion.cursor()

        cursor.execute("""
            INSERT INTO dbo.orden_detalle
            (orden_id, producto, cantidad, precio_unitario, subtotal)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?)
        """, (
            orden_id,
            producto.strip(),
            cantidad,
            precio,
            subtotal
        ))

        nuevo_id = cursor.fetchone()[0]

        recalcular_total(conexion, orden_id)

        conexion.commit()
        cursor.close()

        return jsonify({
            "mensaje": "Detalle creado correctamente",
            "id": nuevo_id,
            "subtotal": float(subtotal)
        }), 201

    except pyodbc.IntegrityError:
        if conexion:
            conexion.rollback()
        return jsonify({"error": "La orden indicada no existe"}), 404

    except Exception as error:
        if conexion:
            conexion.rollback()
        return error_servidor(error)

    finally:
        if conexion:
            conexion.close()


# MODIFICAR UN DETALLE
@app.route("/api/detalles/<int:detalle_id>", methods=["PUT"])
def actualizar_detalle(detalle_id):
    conexion = None

    try:
        datos = request.get_json(silent=True) or {}

        conexion = get_db_connection()
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT orden_id, producto, cantidad, precio_unitario
            FROM dbo.orden_detalle
            WHERE id = ?
        """, (detalle_id,))

        fila = cursor.fetchone()

        if not fila:
            return jsonify({"error": "Detalle no encontrado"}), 404

        orden_id, producto_actual, cantidad_actual, precio_actual = fila

        producto = datos.get("producto", producto_actual)
        cantidad = datos.get("cantidad", cantidad_actual)
        precio = datos.get("precio_unitario", precio_actual)

        if not isinstance(producto, str) or not producto.strip():
            return jsonify({"error": "Producto no valido"}), 400

        if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad <= 0:
            return jsonify({"error": "Cantidad no valida"}), 400

        try:
            precio = Decimal(str(precio))
            if not precio.is_finite() or precio < 0:
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            return jsonify({"error": "Precio no valido"}), 400

        subtotal = (precio * cantidad).quantize(Decimal("0.01"))

        cursor.execute("""
            UPDATE dbo.orden_detalle
            SET producto = ?, cantidad = ?,
                precio_unitario = ?, subtotal = ?
            WHERE id = ?
        """, (
            producto.strip(),
            cantidad,
            precio,
            subtotal,
            detalle_id
        ))

        recalcular_total(conexion, orden_id)

        conexion.commit()
        cursor.close()

        return jsonify({
            "mensaje": "Detalle actualizado correctamente",
            "subtotal": float(subtotal)
        }), 200

    except Exception as error:
        if conexion:
            conexion.rollback()
        return error_servidor(error)

    finally:
        if conexion:
            conexion.close()


# ELIMINAR UN DETALLE
@app.route("/api/detalles/<int:detalle_id>", methods=["DELETE"])
def eliminar_detalle(detalle_id):
    conexion = None

    try:
        conexion = get_db_connection()
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT orden_id
            FROM dbo.orden_detalle
            WHERE id = ?
        """, (detalle_id,))

        fila = cursor.fetchone()

        if not fila:
            return jsonify({"error": "Detalle no encontrado"}), 404

        orden_id = fila[0]

        cursor.execute("""
            DELETE FROM dbo.orden_detalle
            WHERE id = ?
        """, (detalle_id,))

        recalcular_total(conexion, orden_id)

        conexion.commit()
        cursor.close()

        return jsonify({
            "mensaje": "Detalle eliminado y total recalculado"
        }), 200

    except Exception as error:
        if conexion:
            conexion.rollback()
        return error_servidor(error)

    finally:
        if conexion:
            conexion.close()


# ==========================================
# INICIAR SERVIDOR
# ==========================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
