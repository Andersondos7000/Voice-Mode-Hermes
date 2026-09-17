---
title: Voice Mode Hermes — operação e validação
date: 2026-09-12
status: validacao-automatica-concluida-testes-humanos-pendentes
profile: voice-mode-hermes
---

# Voice Mode Hermes — operação e validação

## Situação

O fluxo encadeado instalado foi verificado com áudio sintético em português: Edge TTS → Whisper local → agente Hermes → Edge TTS → reprodução. A abertura do microfone USB também passou em um teste separado de captura. Isso permite iniciar o uso básico; não equivale a aprovação de uma sessão completa com voz humana, nem do modo Realtime.

O usuário solicitou validação automática sem participação imediata. Reconhecimento da fala humana, volume, qualidade percebida, vários turnos e interrupção por fala permanecem pendentes. A API do desktop em `127.0.0.1:9119` respondeu `401` ao diagnóstico sem autenticação; a interface autenticada não foi testada. A rota alternativa de início é a CLI.

## Plano de voz personalizada

O fluxo atual permanece em **Edge TTS**, funcionando como fallback em português. A decisão para voz personalizada é usar **ElevenLabs** com a voz clonada do proprietário, após a ativação de um plano que permita clonagem instantânea via API. O planejamento, o resultado da auditoria, a configuração prevista e o checklist de ativação estão em [PLANO-VOZ-ELEVENLABS.md](PLANO-VOZ-ELEVENLABS.md).

## Instalação e fontes

- Runtime instalado: `C:\Users\Anderson\AppData\Local\hermes\hermes-agent`
- Executável: `C:\Users\Anderson\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe`
- Perfil: `C:\Users\Anderson\AppData\Local\hermes\profiles\voice-mode-hermes`
- Especificação: `workspace\Voice-Mode-Hermes` dentro do perfil.
- Implementação experimental: `workspace\hermes-agent` dentro do perfil.

A especificação contém README, contexto mestre, pesquisa, PRD, arquitetura, plano de implementação, critérios de aceitação e riscos/decisões. O `SOUL.md` do perfil define o agente como engenheiro do projeto, com pt-BR padrão e trabalho na cópia isolada.

O histórico confirma o commit de especificação `680ffda` e os commits experimentais `bad9349` (sessão/eventos/interfaces) e `390d9d7` (VAD/Re­altime). As fases 3–6 constam como não iniciadas no `PROGRESSO.md`. A existência desses commits não comprova integração no runtime instalado.

O runtime ativo contém `hermes_cli/voice.py`, `hermes_cli/cli_voice_mixin.py`, `tools/voice_mode.py` e `tools/tts_tool.py`. Possui fluxo encadeado contínuo e suporte de interrupção próprios. A pasta experimental `voice/` existe somente na cópia isolada. Não concluir que a voz nativa está ausente porque essa pasta não existe na instalação ativa.

Não foi localizado um registro completo dos comandos originais de instalação. Este inventário foi reconstruído a partir dos arquivos, commits, dependências e testes encontrados; não é uma transcrição da instalação original.

## Dependências verificadas

| Componente | Resultado |
|---|---|
| `sounddevice` | instalado, versão 0.5.5; captura passou |
| `faster-whisper` | instalado, versão 1.2.1; transcrição local passou |
| `edge-tts` | instalado, versão 7.2.7; síntese passou |
| `openai`, `websockets` | disponíveis no venv |
| FFmpeg / FFplay | localizados no PATH; reprodução por FFplay passou |
| Microfone padrão | USB Audio CODEC; 15.808 frames capturados no teste de abertura |
| Saída padrão | alto-falantes USB Audio CODEC; reprodução retornou sucesso |

## Configuração validada em 2026-09-12

```yaml
model:
  default: gpt-5.5
  provider: openai-codex
stt:
  enabled: true
  provider: local
  language: pt
  local:
    model: base
voice:
  auto_tts: true
  voice_chat_mode: chained
tts:
  provider: edge
  speed: 1.0
  edge:
    voice: pt-BR-FranciscaNeural
    speed: 1.0
```

Este trecho documenta somente campos de voz e inferência. A configuração real contém outros campos e deve ser preservada.

O modelo anterior `gpt-5.4-mini` era rejeitado pelo backend Codex da conta atual com HTTP 400. Foi substituído por `gpt-5.5`, que respondeu ao teste. O STT foi fixado em local/português, e a resposta falada foi habilitada. Edge TTS necessita conexão de rede; Whisper processa o áudio localmente. A inferência do agente usa o backend Codex autenticado.

## Como iniciar agora

Abra um PowerShell interativo e execute:

```powershell
& 'C:\Users\Anderson\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe' -p voice-mode-hermes -t clarify --cli
```

Ou execute [iniciar_voz.ps1](iniciar_voz.ps1).

Dentro do Hermes:

1. Digite `/voice on` para habilitar o modo de voz.
2. Use `Ctrl+B` para iniciar a gravação; fale uma pergunta curta.
3. Use `Ctrl+B` novamente para parar e transcrever, quando necessário.
4. Aguarde a resposta falada em português.
5. Use `/voice status` para consultar o estado e `/voice off` para desligar.

O atalho `-t clarify` limita ferramentas à de esclarecimento e serve para conversar e validar áudio sem depender dos MCPs do perfil. Não representa a validação de tarefas com ferramentas externas. A ausência de gateway de mensageria não impede esse uso local pela CLI. Para aplicar a configuração em uma sessão já aberta, inicie uma nova sessão do perfil.

## Evidências automáticas

| Verificação | Resultado |
|---|---|
| Síntese inicial | Edge TTS gerou MP3 em pt-BR; aproximadamente 4,22 s |
| STT do áudio sintético | Whisper local retornou pergunta reconhecível; aproximadamente 11,06 s em processo novo; pequenas divergências de palavras |
| Agente com instruções do perfil | respondeu “Dois mais três é cinco”; aproximadamente 17,55 s em processo novo |
| Agente + síntese da resposta | aproximadamente 21,02 s; ambos passaram |
| Reprodução da resposta | retornou sucesso; audição humana não confirmada |
| Cancelamento automático | passou após aguardar o player iniciar; retorno em aproximadamente 0,657 s |
| Microfone | abertura e frames de captura passaram; nenhuma gravação humana foi retida pelo teste automático |

Esses tempos incluem início de processos e carregamento de bibliotecas/modelo. Não são medições p95 de uma sessão aquecida e não comprovam a meta de resposta em 1,2 s nem de interrupção em 150 ms. O cancelamento automático não comprova barge-in disparado pela fala humana.

## Reproduzir a validação

O script [validar_voz.py](validar_voz.py) usa as funções reais da instalação, não mocks. Os estágios devem ser executados sequencialmente: `tts`, `stt`, `agent`, `device`, `playback`, `cancel`.

```powershell
& 'C:\Users\Anderson\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe' '.\validar_voz.py' tts
```

Execute a partir desta pasta e troque `tts` pelo estágio desejado. O estágio opcional `mic --seconds 8` grava e transcreve fala humana e deve ser iniciado quando o usuário estiver pronto. O WAV temporário é removido; a transcrição fica no resultado local.

Resultados e MP3 de teste: `C:\Users\Anderson\AppData\Local\hermes\profiles\voice-mode-hermes\cache\audio\validacao-voz-20260912`. O arquivo `resultado.json` distingue áudio sintético, abertura de dispositivo e testes humanos pendentes. Uma resposta HTTP de erro não é aceita como resposta válida do agente, mesmo se a CLI devolver código zero.

## Próximos testes antes de declarar aprovação completa

- Fala humana em pt-BR e qualidade de reconhecimento.
- Confirmação de audição e qualidade/volume da saída.
- Sessão de vários turnos sem eco ou perda de contexto.
- Interrupção por fala e medição do cancelamento.
- Interface desktop autenticada e seus botões de voz.
- Ferramentas/MCP, recuperação de falha e métricas em sessão aquecida.

## Reverter as alterações deste teste

Os valores anteriores eram `model.default: gpt-5.4-mini` e `voice.auto_tts: false`. As chaves `stt.provider`, `stt.language` e `voice.voice_chat_mode` não estavam explícitas e foram adicionadas nesta validação. Reverter o modelo recupera também sua incompatibilidade observada. Remova somente essas chaves adicionadas se precisar recuperar a seleção automática anterior.


## Nova Arquitetura: Pílula Flutuante (Deepgram Flux + ElevenLabs)

A evolução da interface de voz para um widget flutuante desktop contínuo (Hands-Free com interrupção e orbe animado) está documentada em:
* [ARQUITETURA-PILULA-FLUTUANTE-VOZ.md](ARQUITETURA-PILULA-FLUTUANTE-VOZ.md)
