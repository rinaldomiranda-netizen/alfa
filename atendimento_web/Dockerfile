FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
COPY core ./core
COPY computer ./computer
COPY memory ./memory
COPY modules ./modules
COPY atendimento_web ./atendimento_web
ENV HOST=0.0.0.0
ENV PORT=8080
EXPOSE 8080
CMD ["python", "atendimento_web/app.py"]
