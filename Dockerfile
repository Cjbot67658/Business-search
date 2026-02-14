# Dockerfile (Python 3.11+)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app

# Expose if you need a port (for health checks or webhook)
EXPOSE 8080

CMD ["python", "bot.py"]
