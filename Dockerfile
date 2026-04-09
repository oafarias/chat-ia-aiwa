FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# Coleta arquivos estáticos
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Uso do Daphne para suportar ASGI/WebSockets conforme configurado no settings.py
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "setup.asgi:application"]