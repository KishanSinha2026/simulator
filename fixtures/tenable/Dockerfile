FROM python:3.12-slim
WORKDIR /srv/vpm360
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "if [ \"${DATA:-DB}\" = \"DB\" ]; then alembic upgrade head && python -m scripts.seed_findings && python -m scripts.init_cmdb_db && alembic -c alembic-cmdb.ini upgrade head && python -m scripts.seed_cmdb; fi; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

