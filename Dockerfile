FROM ghcr.io/home-assistant/aarch64-base-python:3.13-alpine3.23

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY app_config.yaml .

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
