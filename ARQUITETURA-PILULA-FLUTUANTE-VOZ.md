---
title: Arquitetura de Voz Contínua — Pílula Flutuante Desktop
date: 2026-09-13
status: em-implantacao
profile: voice-mode-hermes
---

# Arquitetura de Voz Contínua — Pílula Flutuante Desktop

## 1. Visão Geral

Este documento registra a evolução do sistema de voz do Hermes. A arquitetura anterior dependia de linha de comando (/voice on, Ctrl+B), gravação por buffer do Whisper local (que exigia 3 segundos de silêncio para processar) e voz sintética Edge TTS.

A nova arquitetura introduz uma **Pílula Flutuante Desktop (Always-on-Top)** — inspirada na interface de voz do ChatGPT Desktop — integrando streaming em tempo real com fim de turno semântico e síntese neural ultrarrápida.

`	ext
       ┌────────────────────────────────────────────────────────┐
       │             PÍLULA FLUTUANTE (OVERLAY DESKTOP)          │
       │   [ 📝 Texto ]  [ 🎙️ Mic Mute ]  ( 🔵 Orbe )  [ 🔊 Som ] │
       └─────────────────────────▲──────────────────────────────┘
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
   [ OUVINDO: Microfone ]                    [ FALANDO: Alto-falante ]
            │                                         ▲
            ▼                                         │
┌─────────────────────────┐               ┌─────────────────────────┐
│     DEEPGRAM FLUX       │               │       ELEVENLABS        │
│  flux-general-multi     │               │   eleven_flash_v2_5     │
│    language_hint=pt     │               │      Voz: Brian         │
│   (Endpoint /v2/listen) │               │ (nPczCjzI2devNBz1zQrb)  │
│   Streaming + TurnInfo  │               │   Latência: ~75ms       │
└───────────┬─────────────┘               └───────────▲─────────────┘
            │ Transcrição                             │ Resposta falada
            ▼                                         │
┌─────────────────────────────────────────────────────┴─────────────┐
│                       HERMES AGENT CORE                           │
│  • Perfis: voice-mode-hermes / orquestrador-geral                 │
│  • Acesso a MCPs (Obsidian, Supabase, Terminal, Web)              │
│  • Memória contínua e raciocínio de ferramentas                   │
└───────────────────────────────────────────────────────────────────┘
`

---

## 2. Componentes Comprovados e Validados (2026-09-13)

| Componente | Provedor / Modelo | Status de Teste | Comportamento |
|---|---|---|---|
| **Ouvido (STT)** | Deepgram Flux (lux-general-multi, language_hint=pt) | ✅ Autenticado e testado no /v2/listen | Streaming contínuo via WebSocket. Emite eventos TurnInfo com StartOfTurn, Update e end_of_turn_confidence. |
| **Cérebro (Agente)** | Hermes Runtime (hermes-agent) | ✅ Ativo e configurado | Interpreta o comando, consulta memórias, executa ferramentas e gera resposta conversacional direta. |
| **Boca (TTS)** | ElevenLabs (eleven_flash_v2_5, voz Brian) | ✅ Validado na API e reproduzido | Síntese de alta fidelidade em português brasileiro liberada na API do plano Free (10.000 chars/mês). |
| **Fallback TTS** | Microsoft Edge TTS (pt-BR-FranciscaNeural) | ✅ Mantido ativo nos YAMLs | Garante continuidade sem custo se a cota da ElevenLabs esgotar. |

---

## 3. A Interface da Pílula Flutuante

A pílula flutuante é um widget sem bordas que permanece visível sobre qualquer janela do Windows:

* **Orbe Central (Esfera Azul com gradiente):**
  * *Pulsando suave:* Microfone aberto, aguardando fala.
  * *Brilho intenso:* Captando fala do usuário em tempo real.
  * *Ondulação / Rotação:* Hermes pensando / processando ferramentas.
  * *Ondas de voz:* Áudio sendo reproduzido pelos alto-falantes.
* **Interrupção Natural (Barge-in):** Quando o Hermes está falando e o microfone detecta o usuário iniciando uma nova fala (StartOfTurn), o áudio é cortado instantaneamente.
* **Controles Físicos:**
  * Botão de Mute do Microfone.
  * Botão de Mute do Alto-falante.
  * Botão de Pausa / Fechar.

---

## 4. Integração com Perfis Hermes

* oice-mode-hermes: Perfil principal dedicado à conversação contínua.
* orquestrador-geral: Perfil padrão que também agora conta com o ElevenLabs Brian para respostas por áudio (WhatsApp e Gateway).


## 🟢 Status da Implantação e Execução (13/09/2026)

- **Status**: Ativo e em execução (Full-Duplex).
- **Roteamento Escolhido**: **Roteamento por Vocativo (Wake Name)**.
  - Chamar por *'Hermes, ...'* -> Ativa a persona do Hermes (orquestração, automação, Obsidian, WhatsApp).
  - Chamar por *'Antigravity, ...'* -> Ativa a persona do Antigravity IDE (engenharia de software, código, refatoração).
  - Falas subsequentes sem vocativo mantêm a persona ativa em foco.
- **Ouvido (STT)**: Deepgram Flux (lux-general-multi via wss://api.deepgram.com/v2/listen) com detecção de final de fala e barge-in em tempo real.
- **Voz (TTS)**: ElevenLabs Flash v2.5 (eleven_flash_v2_5) com voz Brian (
PczCjzI2devNBz1zQrb) em streaming PCM 16kHz de ultra-baixa latência (< 0.8s).
- **Cérebro Conversacional**: Gemini Flash Lite / 3.6 Flash (latência sub-segundo para fala natural).
- **Launcher e Arquivos**:
  - j:
cloneloating_voice_pill.py
  - j:
clone\iniciar_pilula_voz.bat
  - j:
clone\iniciar_pilula_voz.ps1
  - Atalhos sincronizados no diretório de suporte do Hermes e nesta pasta do Obsidian.

---

## 🟢 Atualização Arquitetural da Boca (TTS): Kokoro-82M Local (17/09/2026)

- **Motivação**: A cota mensal gratuita da ElevenLabs (10.000 caracteres) foi esgotada, gerando falhas de síntese. A nova arquitetura substitui o ElevenLabs por um modelo local open-source sem limites de uso e com zero custo.
- **Modelo TTS Adotado**: **Kokoro-82M ONNX** (kokoro-v1.0.onnx + oices-v1.0.bin).
  - **Voz Principal**: pm_alex (Português do Brasil masculino natural, fluida e expressiva).
  - **Vozes Alternativas**: pm_santa (Codex) e pf_dora (Feminina PT-BR).
  - **Taxa de Amostragem**: 24.000 Hz com speed=1.05 e lang="pt-br".
  - **Consumo**: ~320 MB de RAM. O modelo é instanciado apenas uma vez na inicialização do MouthEngine para evitar overhead de carregamento por turno.
  - **Custo**: R$ 0,00 / Ilimitado (100% offline no hardware local).
- **Ouvido (STT)**: Mantido **Deepgram Flux** (lux-general-multi, WebSocket em tempo real), preservando precisão e detecção de turno semântica.
- **Fallback Automático**: Caso haja qualquer falha na inferência local, o sistema faz fallback instantâneo para o **Microsoft Edge-TTS** (pt-BR-AntonioNeural / pt-BR-FranciscaNeural).
- **Hardware Validado**: Intel Xeon E5-2620 v2 com saída direta no canal USB Audio CODEC ([4]).

---

## ⚡ Atualização Ultrarrápida da Boca (TTS): Cartesia Sonic 2 (17/09/2026)

- **Motivação**: O modelo local Kokoro-82M, embora gratuito e de alta fidelidade, enfrentava lentidão de síntese (10s a 19s por turno) devido à limitação de hardware do processador Intel Xeon E5-2620 v2 (ausência de instruções AVX2 e sem aceleração CUDA).
- **Novo Motor Principal**: **Cartesia Sonic 2** (sonic-2).
  - **Voz**:  7b6f895-78b9-4921-8e10-8a21c99c2e8a (**Rafael - Dynamic Speaker**).
  - **Sotaque / Idioma**: Português Brasileiro nativo masculino, dinâmico e expressivo.
  - **Latência Real Medida**: **0.61s** até o primeiro som sair nas caixas de som (Streaming contínuo de chunks via PCM 24kHz).
  - **Modo de Reprodução**: Streaming em tempo real com buffer alinhado em sd.OutputStream.
  - **Barge-in Instantâneo**: Se o usuário começar a falar enquanto a resposta toca, o stream HTTP e o áudio são interrompidos imediatamente.
- **Cadeia de Resiliência (Fallbacks)**:
  1. **Cartesia Sonic 2** (Voz Rafael - Principal).
  2. **Microsoft Edge-TTS** (pt-BR-AntonioNeural - Fallback instantâneo em nuvem sem custos).
  3. **Kokoro-82M ONNX** (pm_alex - Fallback local de contingência).

### 🔄 Pool Multi-Chave com Auto-Failover (17/09/2026)
- **Chaves Registradas no Pool**:
  1. sk_car_ZiG5g2Ez6ay21dSzNHApVg (Chave Primária)
  2. sk_car_FbPm4GJ5Kfnf6bJm8JF7B8 (Chave Secundária)
- **Mecanismo de Failover Automático**:
  - A pílula consome a chave ativa atual.
  - Se a cota mensal/crédito da primeira chave esgotar (HTTP 402, 429 ou erro), o sistema automaticamente:
    1. Registra no log a migração imediata ([FAILOVER CARTESIA] Chave indisponível. Migrando automaticamente para próxima chave!).
    2. Atualiza o ponteiro de chave ativa para que as próximas falas já usem a chave reserva.
    3. Retenta a síntese instantaneamente sem perder a frase ou o diálogo com o usuário.
  - Se todas as chaves do pool esgotarem, ativa automaticamente o **Microsoft Edge-TTS** (pt-BR-AntonioNeural).
