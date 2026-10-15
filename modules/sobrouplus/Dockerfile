FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY . .
RUN pip install --no-cache-dir cryptography
EXPOSE 8080
CMD ["sh", "-c", "SOBROU_HOST=0.0.0.0 exec python web/app.py"]
