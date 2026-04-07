FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY funda_scraper.py .
COPY config.yaml .
COPY run.sh .
RUN chmod +x run.sh

CMD ["/app/run.sh"]
