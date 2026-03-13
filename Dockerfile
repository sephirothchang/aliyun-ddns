FROM python:3.12-alpine

WORKDIR /app

RUN apk add --no-cache tzdata

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ddns_updater.py /app/ddns_updater.py

CMD ["python", "/app/ddns_updater.py", "--config", "/app/config.yaml"]
