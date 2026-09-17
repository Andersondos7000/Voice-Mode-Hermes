---
title: Plano de voz personalizada — ElevenLabs
date: 2026-09-12
status: aguardando-plano-e-validacao-humana
profile: voice-mode-hermes
---

# Plano de voz personalizada — ElevenLabs

## Decisão

Para o Hermes falar com uma voz personalizada em português brasileiro, a solução escolhida é **ElevenLabs**. Ela já possui integração nativa no runtime do Hermes, não exige GPU local e permite usar uma voz clonada da conta do proprietário.

O modo de conversa continua encadeado:

```text
Microfone USB → Whisper local (PT) → Hermes → ElevenLabs TTS → alto-falantes
```

O modo GPT-Live não é a solução escolhida para este objetivo: ele fornece voz nativa da OpenAI, mas não reutiliza a voz clonada do proprietário. OmniVoice permanece uma alternativa futura sem cobrança por caractere, porém exige uma GPU e um conector próprio para o Hermes.

## Estado comprovado em 2026-09-12

| Item | Resultado |
|---|---|
| Voz escolhida | `Anderson - voz Youtube` |
| Tipo | voz clonada, disponível na conta ElevenLabs |
| Idioma cadastrado | português (`pt`) |
| Identificador da voz | `ByyU3xYemBI1BMLUfMGv` |
| Credencial | presente no perfil como `ELEVENLABS_API_KEY`; o valor não deve ser documentado, exibido ou copiado |
| SDK do Hermes | pacote oficial `elevenlabs` instalado no venv do Hermes |
| Integração Hermes | `tools/tts_tool.py` aceita o provedor `elevenlabs` e usa `tts.elevenlabs.voice_id` e `tts.elevenlabs.model_id` |
| Teste de credencial | autenticou na API sem expor a chave |
| Teste de síntese | recusado pelo provedor com `ivc_not_permitted`: o plano gratuito não permite voz clonada por API |
| Fallback ativo | Edge TTS, voz `pt-BR-FranciscaNeural` |

A recusa da síntese não indica uma chave inválida. Ela confirma que a voz existe, mas que a assinatura atual ainda não autoriza uso de clonagem instantânea pela API.

## Plano de ativação

### 1. Habilitar o uso de voz clonada

Ativar na ElevenLabs um plano que libere **Instant Voice Cloning por API**. O plano Starter ou superior é o ponto de entrada indicado pela ElevenLabs. Antes da compra, conferir preço, créditos e tributos diretamente na página oficial: <https://elevenlabs.io/pricing>.

Não criar nem colar uma nova chave em arquivos, chats ou documentação. A credencial existente deve continuar sendo resolvida pelo ambiente seguro do perfil.

### 2. Ativar o provedor no perfil

Após a assinatura, alterar somente a seção `tts` de `C:\Users\Anderson\AppData\Local\hermes\profiles\voice-mode-hermes\config.yaml`:

```yaml
tts:
  provider: elevenlabs
  speed: 1.0
  elevenlabs:
    voice_id: ByyU3xYemBI1BMLUfMGv
    model_id: eleven_flash_v2_5
```

O identificador da voz é público para a conta, mas a chave de API nunca entra nesse arquivo.

Modelo inicial recomendado: `eleven_flash_v2_5`, por ter menor latência para diálogo. Se a amostra aprovada pelo usuário perder semelhança com a voz original, testar `eleven_multilingual_v2`, que prioriza estabilidade e fidelidade em português.

### 3. Validar síntese isolada

Gerar uma frase curta pelo próprio `tools.tts_tool` do Hermes. Critérios:

- a síntese retorna sucesso e cria áudio não vazio;
- a voz é a clonada, em português brasileiro;
- não há chave ou token no terminal, nos logs ou na resposta;
- o resultado não desativa nem altera a cadeia de STT.

Frase de controle:

> Olá, Anderson. Sou o Hermes. Minha voz está pronta para ajudar você.

### 4. Validar conversa ponta a ponta

Com microfone e alto-falantes USB selecionados, executar três turnos reais:

1. pergunta simples;
2. pedido com nome, número ou termo em português para checar pronúncia;
3. interrupção enquanto o Hermes fala.

Registrar qualidade percebida, latência, volume, transcrição e se a interrupção cancela a fala corretamente.

### 5. Operação segura

- Manter Edge TTS configurado como fallback; não remover sua seção do YAML.
- Se a ElevenLabs devolver falha de autenticação, saldo ou rede, restaurar `tts.provider: edge` e informar o motivo.
- Evitar respostas faladas excessivamente longas; preferir frases curtas durante conversa para controlar custo e latência.
- Acompanhar consumo no painel da ElevenLabs. A API desconta o mesmo saldo de créditos da conta.

## Estimativa de consumo

Os valores são estimativas de planejamento e precisam ser confirmados no painel no momento da contratação.

| Modelo | Consumo de referência | Rendimento estimado com 30 mil créditos |
|---|---:|---:|
| `eleven_multilingual_v2` | 1 crédito por caractere | cerca de 27–33 minutos de fala |
| `eleven_flash_v2_5` | cerca de 0,5 crédito por caractere | cerca de 55–65 minutos de fala |

Esses minutos correspondem somente ao áudio falado pelo Hermes. A captura do microfone e a transcrição atual usam Whisper local e não consomem créditos da ElevenLabs.

Fonte de preço e consumo: <https://elevenlabs.io/pricing/api> e <https://help.elevenlabs.io/hc/en-us/articles/21811236079505-How-do-I-find-the-model-ID>.

## Alternativas avaliadas

| Alternativa | Decisão | Motivo |
|---|---|---|
| GPT-Live | não usar para esta voz | não aceita a voz clonada do proprietário; também requer saldo OpenAI API |
| Deepgram Flux TTS | não usar | as vozes avaliadas são em inglês |
| Gemini Live | não usar como voz do Hermes | seria uma nova integração e não preserva a voz clonada escolhida |
| OmniVoice | manter em observação | pode eliminar cobrança por caractere, mas exige GPU e serviço/conector próprio |
| Edge TTS | manter | fallback atual, gratuito e já validado em PT-BR |

## Critério de conclusão

O plano será considerado concluído somente quando:

- o plano ElevenLabs estiver apto a usar a voz clonada por API;
- uma síntese real do Hermes for aprovada pelo usuário;
- uma conversa humana de três turnos, incluindo interrupção, passar;
- Edge TTS continuar disponível como fallback;
- este documento e o `README.md` refletirem a configuração final, sem segredos.
