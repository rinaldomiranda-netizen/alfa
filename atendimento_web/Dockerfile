FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    RMD_ATENDIMENTO_DADOS=/dados \
    RMD_ATRAS_DE_PROXY=1
# A plataforma usa só a biblioteca padrão do Python.
COPY modules/atendimento ./modules/atendimento
COPY atendimento_web ./atendimento_web
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
