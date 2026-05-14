ARG BUILD_FROM=python:3.12-alpine
FROM ${BUILD_FROM}

WORKDIR /app

COPY requirements.txt .
RUN apk add --no-cache gcc musl-dev libffi-dev && \
    pip3 install --no-cache-dir -r requirements.txt && \
    apk del gcc musl-dev libffi-dev

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY app_config.yaml .

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
