FROM python:3.13-slim

WORKDIR /app

# Keep logs unbuffered and make host/port configurable.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

COPY . /app

EXPOSE 8000

CMD ["python3", "server.py"]
