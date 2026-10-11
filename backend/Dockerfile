FROM python:3.12-slim

# Шрифт с кириллицей для генерации PDF-профилей
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY fsp_mock ./fsp_mock
COPY validation ./validation
COPY tests ./tests

ENV PYTHONUNBUFFERED=1 PDF_FONT_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
EXPOSE 8000
# SEED_ON_START=1 — пересоздать демо-данные при старте (удобно для стенда проверки)
CMD ["sh", "-c", "if [ \"$SEED_ON_START\" = \"1\" ]; then python -m app.seed; fi && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
