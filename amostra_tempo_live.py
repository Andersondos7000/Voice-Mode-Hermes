"""One bounded GPT-Live voice sample; no microphone or profile changes."""
import asyncio
import base64
import json
import os
from pathlib import Path
import sys
import time
import wave

RUNTIME = Path(r'C:\Users\Anderson\AppData\Local\hermes\hermes-agent')
os.environ['HERMES_HOME'] = r'C:\Users\Anderson\AppData\Local\hermes\profiles\voice-mode-hermes'
sys.path.insert(0, str(RUNTIME))
from tools.voice_live import _resolve_credentials
from websockets.asyncio.client import connect


async def main():
    key, base = _resolve_credentials({})
    if not key or base != 'https://api.openai.com/v1':
        raise RuntimeError('Direct OpenAI credential unavailable')
    output = Path(__file__).with_name('tempo-gpt-live.wav')
    if output.exists():
        raise RuntimeError('Sample already exists; refusing overwrite')
    chunks = []
    transcript = []
    usage = None
    started = False
    closing = False
    last_audio = None
    deadline = time.monotonic() + 40
    async with connect('wss://api.openai.com/v1/live/sessions',
                       additional_headers={'Authorization': 'Bearer ' + key},
                       open_timeout=15, close_timeout=3, max_size=8_000_000) as ws:
        await ws.send(json.dumps({
            'type': 'session.start', 'event_id': 'sample_start',
            'session': {
                'model': 'gpt-live-1',
                'instructions': 'Fale em português brasileiro, naturalmente. Esta é uma amostra de voz. Diga somente a frase fornecida, uma única vez, e depois fique em silêncio. Não delegue tarefas.',
                'audio': {'format': {'type': 'audio/pcm', 'rate': 24000},
                          'output': {'voice': 'tempo'}},
                'delegation': {'type': 'client'},
            },
        }))
        silence = base64.b64encode(bytes(4800)).decode('ascii')
        while time.monotonic() < deadline:
            try:
                event = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.1))
            except asyncio.TimeoutError:
                event = {}
            kind = event.get('type')
            if kind == 'session.started':
                started = True
                print('GPT-Live started; voice Tempo', flush=True)
                await ws.send(json.dumps({
                    'type': 'session.instructions.append', 'event_id': 'sample_phrase',
                    'delegation_id': None,
                    'content': 'Diga agora, uma única vez: Olá, Anderson. Sou o Hermes. Vamos conversar em português e trabalhar nos seus projetos. Depois fique em silêncio.',
                }, ensure_ascii=False))
            elif kind == 'session.output_audio.delta':
                chunks.append(base64.b64decode(event['delta']))
                last_audio = time.monotonic()
            elif kind == 'session.output_transcript.delta':
                transcript.append(event.get('delta', ''))
            elif kind == 'session.closed':
                usage = event.get('usage')
                print('Final session usage:', json.dumps(usage), flush=True)
                break
            elif kind == 'error':
                error = event.get('error', {})
                print('API error:', error.get('code'), str(error.get('message', ''))[:300], flush=True)
                if started and not closing:
                    closing = True
                    await ws.send(json.dumps({'type': 'session.close'}))
                elif not started:
                    break
            now = time.monotonic()
            if started and not closing:
                if (last_audio and now - last_audio > 2) or now > deadline - 12:
                    closing = True
                    await ws.send(json.dumps({'type': 'session.close'}))
                else:
                    await ws.send(json.dumps({'type': 'session.input_audio.append', 'audio': silence}))
        if not chunks:
            raise RuntimeError('No GPT-Live audio received; no sample generated')
    with wave.open(str(output), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b''.join(chunks))
    print('Audio:', output)
    print('Audio seconds:', round(sum(map(len, chunks)) / 48000, 2))
    print('Transcript:', ''.join(transcript))
    print('Final usage confirmed:', usage is not None)


if __name__ == '__main__':
    asyncio.run(main())
