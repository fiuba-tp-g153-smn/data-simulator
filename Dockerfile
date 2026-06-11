FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY settings.json .
COPY src/ src/

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

EXPOSE 6030

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:6030/health')"

CMD ["python", "-m", "feed_simulator.main"]
