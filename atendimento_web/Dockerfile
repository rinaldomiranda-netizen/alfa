# Etapa 1: compila a shell React completa do ALFA.
FROM node:22-alpine AS frontend
WORKDIR /src
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Etapa 2: servidor Python que expõe o dashboard completo e o Atendimento.
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
COPY core ./core
COPY computer ./computer
COPY memory ./memory
COPY security ./security
COPY modules ./modules
COPY atendimento_web ./atendimento_web
COPY --from=frontend /src/dist ./frontend_dist
RUN touch /app/core/__init__.py \
    /app/modules/__init__.py \
    /app/modules/atendimento/__init__.py \
    /app/computer/__init__.py \
    /app/memory/__init__.py \
    /app/security/__init__.py
ENV HOST=0.0.0.0
ENV PORT=8080
EXPOSE 8080
CMD ["python", "atendimento_web/app.py"]
