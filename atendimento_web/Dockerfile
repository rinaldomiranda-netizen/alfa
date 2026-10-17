# Etapa 1: instala a ponte do WhatsApp por QR Code (Node). Se falhar, o sistema sobe igual, só sem o QR.
FROM node:22-bookworm-slim AS ponte
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /ponte
COPY atendimento_web/whatsapp_qr/package.json ./
RUN npm install --omit=dev --no-audit --no-fund || (echo "AVISO: ponte do WhatsApp nao instalada" && mkdir -p node_modules)

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    RMD_ATENDIMENTO_DADOS=/dados \
    RMD_ATRAS_DE_PROXY=1
# A plataforma usa só a biblioteca padrão do Python.
COPY modules/atendimento ./modules/atendimento
COPY atendimento_web ./atendimento_web
# Ponte do WhatsApp por QR Code: o Node e as bibliotecas vêm da etapa 1 (só escuta em 127.0.0.1).
COPY --from=ponte /usr/local/bin/node /usr/local/bin/node
COPY --from=ponte /ponte/node_modules ./atendimento_web/whatsapp_qr/node_modules
# Sobrou+ (sistema separado, processo e dados próprios). Só roda quando o serviço usa o porteiro.py.
COPY modules/sobrouplus ./modules/sobrouplus
# Central de Pesquisas: só as telas (os dados ficam no Supabase central-pesquisas). Servida pelo porteiro em /pesquisas.
COPY modules/central_pesquisas ./modules/central_pesquisas
# Só o Sobrou+ usa: aviso no celular com o app fechado (Web Push, criptografia oficial). Sem ele, o resto funciona igual.
RUN pip install --no-cache-dir cryptography
EXPOSE 8080
# Os dados ficam em /dados: no Railway, ligar um volume nesse caminho
# (em Docker comum: -v rmd_dados:/dados). O Railway informa a porta em
# $PORT e coloca o HTTPS na frente; o servidor escuta em 0.0.0.0.
CMD ["sh", "-c", "python atendimento_web/app.py --host 0.0.0.0 --porta ${PORT:-8080}"]
