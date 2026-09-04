FROM python:3.11-slim

# --- Proksi (internetsiz VM: build vaqti pip Squid orqali chiqadi) -----------
# .env -> docker-compose build.args -> shu ARG'lar. Bo'sh bo'lsa proksisiz.
# NO_PROXY ga ichki compose hostlarini (db, backend, web) qo'shing.
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG NO_PROXY=
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# apt kerak emas: asyncpg/bcrypt/pydantic-core — hammasi manylinux wheel bilan
# keladi; libpq/psycopg ishlatilmaydi; healthcheck python bilan (curl'siz).
# Shu tufayli internetsiz VM'da build faqat pip proksisini talab qiladi.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
# `bash` bilan chaqiramiz — bind-mount host fayl exec bitisiz bo'lsa ham ishlaydi
ENTRYPOINT ["bash", "/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
