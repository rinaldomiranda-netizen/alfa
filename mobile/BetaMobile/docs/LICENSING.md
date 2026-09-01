# Licenciamento do BETA Mobile

Arquitetura de autorização por módulo, sem código manual de ativação.
Ver também `ACTIVATION.md` para o passo a passo de como ativar um
aparelho (online e presencial).

## Hierarquia de autoridade

`PUBLIC` (visitante do Totem) → `OPERATOR` (PIN de manutenção) →
`COMPANY_ADMIN` (conceito, sem tela própria ainda) → `BETA_DEVELOPER`
(PIN separado) → `BETA_OWNER` (senha própria, autoridade máxima sobre
licenciamento). Um nível nunca vira outro sozinho — o PIN operacional
nunca dá acesso de desenvolvedor, e nenhum dos dois dá acesso de
proprietário.

Ver `com.beta.mobile.licensing.Nivel`.

## Autenticação x autorização

São coisas diferentes e nunca se misturam neste código:

- **Autenticação** = "quem é você?" — PIN de manutenção, PIN de
  desenvolvedor, senha do proprietário (`CredencialProprietario`,
  PBKDF2 + sal, sem senha de fábrica).
- **Autorização** = "o que este aparelho pode usar?" — decidida
  inteiramente por `GerenciadorLicenca`, a partir de uma licença
  assinada (ou do conjunto DEMO fixo, na ausência de uma).

A senha do proprietário **nunca** vira licença, nunca autoriza um
módulo por si só — ela só abre a porta pra mexer na licença.

## Módulos

`com.beta.mobile.licensing.Modulo` — enum fechado, default DENY.
Nunca remover um valor já existente (licenças antigas assinadas
referenciam esses nomes pelo texto do enum). Módulos atuais:
`TOTEM, APLICATIVO, ASSISTENTE, DESKTOP, INTEGRACAO_EMPRESA, CATALOGO,
AUTOMACAO, ACESSIBILIDADE, CAMERA, RECONHECIMENTO_FACIAL, BETA_CLOUD,
MARKETPLACE, ATUALIZACAO, VOZ, CAMERA_PRESENCA, CAMERA_CONTAGEM,
PONTO_FUNCIONARIO, PAGAMENTO`.

Sem licença local ativa, o aparelho roda em **modo DEMO** com um
conjunto fixo e reduzido de módulos (nunca os sensíveis: integração de
empresa, automação, câmeras, reconhecimento facial, BETA-CLOUD,
marketplace, atualização, ponto, pagamento).

Autorização por licença nunca ignora as permissões do sistema
operacional/Android: um módulo licenciado (ex. `CAMERA_PRESENCA`) só
funciona de verdade se a permissão `android.permission.CAMERA` também
estiver concedida. Licença e permissão são checagens independentes.

## Device binding

`Preferencias.deviceId` — UUID gerado e persistido na primeira
execução, nunca derivado de nome do aparelho/usuário/MAC. Uma licença
só ativa se o `device_id` dela bater exatamente com o do aparelho.
Copiar a instalação pra outro aparelho gera um `device_id` novo, então
a licença antiga simplesmente não corresponde — nunca ativa sozinha.

## Assinatura digital

RSA-2048, `SHA256withRSA`. A chave privada existe **só** em
`licensing_tools/beta_owner_private_key.pem`, numa pasta fora de
`mobile/BetaMobile` — nunca compilada no APK, nunca num pendrive, nunca
no computador do cliente. O aparelho carrega só a chave pública,
embutida em `LicenseVerifier.kt`, usada exclusivamente para verificar.

Uma licença offline nunca é um `"enabled": true` simples — é sempre o
par (corpo JSON, assinatura) verificado byte a byte antes de qualquer
decisão de autorização.

## Online x presencial

Não existe hoje um endpoint real de ativação no BETA-CLOUD (fora do
escopo autorizado desta sessão — ver limitações no relatório da
sessão). Por isso:

- O aparelho **nunca** declara ter enviado ou recebido nada de um
  BETA-CLOUD que não está configurado.
- Com internet, o painel do proprietário mostra isso com todas as
  letras e aponta para o caminho presencial.
- Sem internet, mostra diretamente "ATIVAÇÃO PRESENCIAL NECESSÁRIA".

Ver `ACTIVATION.md` para o passo a passo real (o único caminho de
ativação disponível hoje).

## Transferência

Trocar de aparelho sempre gera um `device_id` novo. A licença antiga
**nunca** migra automaticamente. O proprietário emite uma licença nova
para o `device_id` novo (mesmo `emitir_licenca.py`) e, se quiser,
revoga a antiga localmente no aparelho antigo.

## Revogação

`REVOGAR LICENÇA LOCAL` no painel do proprietário limpa só a licença
deste aparelho — nunca apaga nenhum outro dado. Revogação **remota**
de verdade (o aparelho "descobrir sozinho" que foi revogado ao
reconectar) depende do mesmo endpoint de BETA-CLOUD que a ativação
online — pendente pelo mesmo motivo.
