# Ativação de um aparelho — passo a passo

Nenhum dos dois caminhos abaixo usa um código de ativação digitado
("código de 8 caracteres", "código por WhatsApp" etc.). A autorização
sempre passa por uma licença assinada digitalmente, nunca por um
código curto sem vínculo criptográfico com o aparelho.

## Caminho 1 — aparelho com internet (hoje, sem BETA-CLOUD real)

1. No aparelho: MODO DE MANUTENÇÃO → ÁREA DO DESENVOLVEDOR → "Área do
   proprietário" → autenticar com a senha do proprietário.
2. O painel mostra se há internet. **Mesmo com internet**, ele deixa
   claro que a ativação remota via BETA-CLOUD não está configurada
   nesta instalação (não existe hoje o endpoint que receberia um
   pedido de ativação) — e não finge um envio.
3. O caminho a seguir é o presencial (abaixo).

Quando o BETA-CLOUD tiver esse endpoint (fora do escopo desta sessão),
o fluxo será: o aparelho novo registra o `device_id` e cria um pedido
de ativação com status `PENDING_APPROVAL`; o proprietário revisa
remotamente (cliente, organização, aparelho, plataforma, data,
módulos solicitados) e aprova marcando módulos num checklist — sem
código manual, exatamente como o caminho presencial abaixo já faz
localmente.

## Caminho 2 — ativação presencial (o único disponível hoje)

1. No aparelho: MODO DE MANUTENÇÃO → ÁREA DO DESENVOLVEDOR → "Área do
   proprietário" → autenticar com a senha do proprietário.
2. Sem internet, o painel já mostra direto: **"ATIVAÇÃO PRESENCIAL
   NECESSÁRIA"**.
3. Em "Selecionar módulos", marque os módulos desejados (checklist,
   nunca texto digitado) e toque em **GERAR PEDIDO DE ATIVAÇÃO**. O
   painel monta o comando exato pra rodar em `licensing_tools/` —
   já com o `device_id` certo e os módulos escolhidos, nada pra
   copiar à mão.
4. Copie o comando (botão "COPIAR COMANDO") e leve pra máquina segura
   do proprietário (a única que tem a chave privada).
5. Rode `emitir_licenca.py` nessa máquina (ajuste `--customer-id`/
   `--organization-id`; pode usar `--interativo` pra reconferir os
   módulos num checklist numerado antes de assinar). Isso gera o
   arquivo `<device_id>.beta-license`, assinado com a chave privada
   que nunca sai dessa máquina.
6. De volta ao aparelho, em "Ativar licença local": toque em
   **IMPORTAR ARQUIVO .beta-license** e escolha o arquivo (via
   pendrive, e-mail, nuvem — como preferir transferir o arquivo), ou
   cole o conteúdo no campo de texto como alternativa.
7. O aparelho verifica a assinatura, o `device_id` e a validade antes
   de ativar. Sucesso: "Licença ativada com sucesso." e o status passa
   a mostrar os módulos reais da licença.

## Revogar

Painel do proprietário → "REVOGAR LICENÇA LOCAL". Volta ao modo DEMO
imediatamente, sem apagar nenhum outro dado do aparelho.

## Transferir para outro aparelho

O aparelho novo tem um `device_id` diferente — a licença antiga nunca
ativa nele sozinha. Repita o Caminho 2 no aparelho novo, gerando uma
licença nova para o `device_id` novo. Revogue a licença do aparelho
antigo se ele não for mais usado.

## O que NUNCA fazer

- Nunca digitar ou aceitar um "código de ativação" curto e
  desvinculado do `device_id`.
- Nunca copiar a chave privada para o aparelho, pendrive ou máquina do
  cliente — ela mora só em `licensing_tools/`.
- Nunca declarar uma ativação remota "funcionando" sem um endpoint
  real de BETA-CLOUD por trás.
