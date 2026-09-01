# BETA Mobile

**Status: primeira versão implementada e compilada de verdade** (ver
`BetaMobile/`) — Android/Kotlin + Jetpack Compose, build real com
Gradle 8.11.1 + AGP 8.7.2, produzindo um APK debug instalável.

## Arquitetura

```
BETA Mobile (Kotlin/Compose) -> BetaCloudApi (contrato de api/contrato.py) -> BETA-CLOUD/serviços
                              -> voz nativa do Android (SpeechRecognizer/TextToSpeech)
                              -> catálogo de teste local (assets/catalogo_teste.json)
```

Nenhum "cérebro" novo: Planner, Verifier, Tool Registry, Skills e
Permissões continuam sendo responsabilidade exclusiva do BETA Core
(desktop). O app fala com essa camada só através da API (quando
configurada); localmente, resolve por conta própria só o que é
justificável num cliente fino (voz on-device, catálogo de
demonstração, preferências de acessibilidade).

## Como abrir/compilar

Projeto Gradle padrão — abrir a pasta `BetaMobile/` no Android
Studio, ou compilar por linha de comando:

```
gradle assembleDebug
```

(`local.properties` aponta para o SDK desta máquina — o Android
Studio recria esse arquivo sozinho ao abrir o projeto em outra
máquina; nunca precisa editar à mão.)

## O que já funciona (ver relatório da sessão para detalhes)

- Seletor de modo (Discreto/Aplicativo/Totem) com preferência salva.
- Voz: captura sob demanda (SpeechRecognizer) + resposta falada
  (TextToSpeech) — nativos do Android, sem duplicar Whisper/Edge TTS.
- Catálogo de teste local (produto/preço/categoria) respondendo por
  voz ou texto — nunca inventa produto/preço/estoque.
- Acessibilidade básica: 3 tamanhos de fonte, alto contraste.
- Câmera frontal opcional (prévia ao vivo, sem gravação contínua).
- Cliente BETA-CLOUD preparado (mesmo contrato do desktop) — sem URL/
  chave configuradas no build, o app funciona 100% offline.

## O que NÃO está nesta versão

- Wake word contínua (Android não expõe hotword sempre-ativo pra
  apps de terceiros sem hardware dedicado).
- Reconhecimento facial (só a captura de câmera existe).
- Layout adaptativo formal para tablet (Compose já se ajusta de forma
  básica; sem `WindowSizeClass` dedicado ainda).
- Teste em dispositivo físico ou emulador rodando (ver limitações).
