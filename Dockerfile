FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY web_app ./web_app

RUN groupadd -g 1000 app && useradd -u 1000 -g app -M -d /app app \
    && mkdir -p /data && chown app:app /data /app
USER app

ENV APP_DATA_DIR=/data
VOLUME /data
EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "web_app.app:create_app()"]
