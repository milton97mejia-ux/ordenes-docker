FROM python:3.12-slim

WORKDIR /app

# Copiar e instalar dependencias
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copiar archivos de Django
COPY . .

# Crear usuario sin privilegios
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --create-home appuser \
    && chown -R appuser:appgroup /app

# Configuracion de Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Ejecutar con usuario sin privilegios
USER appuser

# Puerto de Django
EXPOSE 8000

# Iniciar servidor Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]