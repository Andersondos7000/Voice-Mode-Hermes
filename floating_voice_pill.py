"""
Floating Voice Pill - 70% Compact Scale (Hermes, Antigravity, Codex)
- High-Fidelity Sleek Dark Glass UI (Exact replica of reference, 70% scaled: 450x64)
- STT: Deepgram Flux (flux-general-multi, Portuguese, wss://api.deepgram.com/v2/listen)
- Anti-Echo & Anti-Spam: Single-flight concurrency lock, debouncing, speaker isolation
- Brain: Fast Gemini Flash Lite with Phonetic Vocative Routing ('Hermes', 'Antigravity', 'Codex')
- TTS: Cartesia Sonic 2 (Streaming Ultra-Fast, Voice: Rafael, pt-BR)
"""

import os
import sys
import time
import math
import json
import queue
import re
import threading
import asyncio
import requests
import numpy as np
import sounddevice as sd
import websockets
import io
import av
import edge_tts
from kokoro_onnx import Kokoro
import tkinter as tk
from PIL import Image, ImageDraw, ImageFont, ImageTk

sys.stdout.reconfigure(line_buffering=True)

# ─────────────────────────────────────────────────────────────────────────────
# 0. Single-Instance Auto-Takeover (Mata instâncias antigas ou fantasmas e abre a nova)
# ─────────────────────────────────────────────────────────────────────────────
import psutil

def ensure_single_instance():
    current_pid = os.getpid()
    parent_pid = os.getppid()
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pid = proc.info['pid']
                if pid not in (current_pid, parent_pid):
                    pname = (proc.info['name'] or '').lower()
                    if 'python' in pname:
                        cmdline = " ".join(proc.info['cmdline'] or [])
                        if "floating_voice_pill.py" in cmdline:
                            print(f"[CLEANUP] Encerrando instância anterior (PID {pid})...")
                            proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as e:
        print(f"[CLEANUP] Aviso ao verificar instâncias: {e}")

ensure_single_instance()
# ─────────────────────────────────────────────────────────────────────────────
# 1. Configuration & Key Management
# ─────────────────────────────────────────────────────────────────────────────
def get_env_var(name, default=""):
    env_paths = [
        r"C:\Users\Anderson\AppData\Local\hermes\profiles\voice-mode-hermes\.env",
        r"C:\Users\Anderson\AppData\Local\hermes\.env",
        r"C:\Users\Anderson\AppData\Local\hermes\profiles\orquestrador-geral\.env"
    ]
    for p in env_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(f"{name}="):
                            val = line.split("=", 1)[1].strip()
                            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                                val = val[1:-1]
                            return val
            except Exception:
                pass
    return os.environ.get(name, default)

DEEPGRAM_API_KEY = get_env_var("DEEPGRAM_API_KEY")
ELEVENLABS_API_KEY = get_env_var("ELEVENLABS_API_KEY")
GOOGLE_API_KEY = get_env_var("GOOGLE_API_KEY")
ELEVENLABS_VOICE_ID = "nPczCjzI2devNBz1zQrb"
ELEVENLABS_MODEL_ID = "eleven_flash_v2_5"

SAMPLE_RATE = 16000
CHUNK_SIZE = 1024

raw_cartesia_keys = get_env_var("CARTESIA_API_KEYS", "")
if raw_cartesia_keys:
    CARTESIA_API_KEYS = [k.strip() for k in raw_cartesia_keys.split(",") if k.strip()]
else:
    CARTESIA_API_KEYS = []

single_cartesia_key = get_env_var("CARTESIA_API_KEY", "")
if single_cartesia_key and single_cartesia_key not in CARTESIA_API_KEYS:
    CARTESIA_API_KEYS.insert(0, single_cartesia_key)

# Chaves padrão registradas no pool
default_keys = [
    "sk_car_ZiG5g2Ez6ay21dSzNHApVg",
    "sk_car_FbPm4GJ5Kfnf6bJm8JF7B8"
]
for dk in default_keys:
    if dk not in CARTESIA_API_KEYS:
        CARTESIA_API_KEYS.append(dk)

CARTESIA_VOICE_ID = get_env_var("CARTESIA_VOICE_ID", "07b6f895-78b9-4921-8e10-8a21c99c2e8a") # Rafael
CARTESIA_MODEL_ID = "sonic-2"

KOKORO_MODEL_DIR = r"J:\pilula_voz\kokoro_model"
KOKORO_ONNX_PATH = os.path.join(KOKORO_MODEL_DIR, "kokoro-v1.0.onnx")
KOKORO_VOICES_PATH = os.path.join(KOKORO_MODEL_DIR, "voices-v1.0.bin")


def find_microphone_device():
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] > 0 and "usb.mic" in dev["name"].lower():
            print(f"[AUDIO] Microfone ativo selecionado: [{idx}] {dev['name']}")
            return idx
    default_in = sd.default.device[0]
    print(f"[AUDIO] Microfone padrao selecionado: [{default_in}] {devices[default_in]['name']}")
    return default_in

def find_speaker_device():
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        if dev["max_output_channels"] > 0 and "usb audio" in dev["name"].lower():
            print(f"[AUDIO] Saída de som selecionada: [{idx}] {dev['name']}")
            return idx
    default_out = sd.default.device[1]
    print(f"[AUDIO] Saída de som padrão: [{default_out}] {devices[default_out]['name']}")
    return default_out

# ─────────────────────────────────────────────────────────────────────────────
# 2. Multi-Agent Vocative Router with Phonetic Normalization
# ─────────────────────────────────────────────────────────────────────────────
class VoiceRouter:
    def __init__(self):
        self.active_target = "antigravity"
        self.history = {
            "hermes": [],
            "antigravity": [],
            "codex": []
        }

    def route(self, text):
        t = text.strip()
        lower_t = t.lower()

        # Phonetic normalization for known STT transcription drift
        # Hermes: "emerson", "ermes", "ermez", "hremes"
        # Antigravity: "antigráficos", "antigrav", "anti-gravity", "antigraviti"
        # Codex: "index", "códes", "code-x"

        # Hermes detection (including phonetic drift: irmãs, irmãos, emerson)
        if re.search(r'\b(hermes|ermes|emerson|hremes|ermez|irmãs|irmas|irmãos|irmaos)\b', lower_t):
            self.active_target = "hermes"
            prompt = re.sub(r'^(?:ei|olá|ola|opa)?[,\s]*(?:hermes|ermes|emerson|hremes|ermez|irmãs|irmas|irmãos|irmaos)[,\s\.\!\:\?]*', '', t, flags=re.IGNORECASE).strip()
            return "hermes", prompt if prompt else t

        # Antigravity detection
        if re.search(r'\b(antigravity|antigraviti|antigráficos|antigrav|anti-gravity|anti gravity)\b', lower_t):
            self.active_target = "antigravity"
            prompt = re.sub(r'^(?:ei\s+|olá\s+|opa\s+)?(?:antigravity|antigraviti|antigráficos|antigrav|anti-gravity|anti gravity)[\s,\.\!\:\?]*', '', t, flags=re.IGNORECASE).strip()
            return "antigravity", prompt if prompt else t

        # Codex detection
        if re.search(r'\b(codex|code-x|códes|codec)\b', lower_t):
            self.active_target = "codex"
            prompt = re.sub(r'^(?:ei\s+|olá\s+|opa\s+)?(?:codex|code-x|códes|codec)[\s,\.\!\:\?]*', '', t, flags=re.IGNORECASE).strip()
            return "codex", prompt if prompt else t

        return self.active_target, t

    def get_system_prompt(self, target):
        if target == "hermes":
            return (
                "Você é Hermes, o orquestrador pessoal e assistente inteligente de Anderson. "
                "Você cuida do ecossistema geral, Obsidian, automações, tarefas e WhatsApp. "
                "Responda em Português do Brasil com linguagem natural, concisa e conversacional para voz. "
                "NUNCA use formatações markdown, asteriscos, numerações ou tabelas. "
                "Fale de forma direta em 1 a 3 frases."
            )
        elif target == "codex":
            return (
                "Você é Codex, o assistente sênior focado em automação de tarefas, testes e implementação pragmática de código. "
                "Responda em Português do Brasil de forma rápida, objetiva e prática para voz em 1 a 3 frases fluidas."
            )
        else:
            return (
                "Você é Antigravity, o assistente avançado de engenharia de software e programação em par no IDE do Google DeepMind. "
                "Você ajuda o Anderson a programar, depurar e refatorar em Go, Python, TypeScript e PowerShell. "
                "Responda em Português do Brasil de forma técnica, precisa e concisa para voz. "
                "NUNCA use markdown, blocos de código ou caracteres especiais. "
                "Fale a resposta de forma direta em 1 a 3 frases."
            )

# ─────────────────────────────────────────────────────────────────────────────
# 3. Brain Engine (Fast Gemini Flash Lite with Strict Timeout & Fallback)
# ─────────────────────────────────────────────────────────────────────────────
class BrainEngine:
    def __init__(self, router):
        self.router = router
        self.brain_dir = r"C:\Users\Anderson\.gemini\antigravity-ide\brain"
        self.codex_proc_file = r"C:\Users\Anderson\.codex\process_manager\chat_processes.json"

    def get_ide_context(self):
        import json
        import datetime
        context_blocks = []
        
        # 1. Antigravity IDE: Descobre dinamicamente todas as conversas recentes ativas
        if os.path.exists(self.brain_dir):
            try:
                entries = []
                for item in os.listdir(self.brain_dir):
                    p = os.path.join(self.brain_dir, item)
                    if os.path.isdir(p) and not item.startswith('.'):
                        t_path = os.path.join(p, ".system_generated", "logs", "transcript.jsonl")
                        if os.path.exists(t_path):
                            try:
                                mtime = os.path.getmtime(t_path)
                                entries.append((mtime, item, t_path))
                            except:
                                pass
                
                # Ordena por mais recentemente modificada
                entries.sort(key=lambda x: x[0], reverse=True)
                
                # Pega as 2 conversas mais recentes abertas
                for idx, (mtime, cid, t_path) in enumerate(entries[:2]):
                    dt_str = datetime.datetime.fromtimestamp(mtime).strftime('%H:%M:%S')
                    try:
                        with open(t_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                        
                        chat_turns = []
                        active_doc = ""
                        for line in lines[-120:]:
                            try:
                                d = json.loads(line.strip())
                                tp = d.get('type')
                                c = d.get('content', '')
                                if tp == 'USER_INPUT' and isinstance(c, str) and c.strip():
                                    clean_c = c.replace('<USER_REQUEST>', '').replace('</USER_REQUEST>', '').strip()
                                    if '<ADDITIONAL_METADATA>' in clean_c:
                                        meta_part = clean_c.split('<ADDITIONAL_METADATA>')[1]
                                        for meta_line in meta_part.splitlines():
                                            if 'Active Document:' in meta_line:
                                                active_doc = meta_line.replace('Active Document:', '').strip()
                                        clean_c = clean_c.split('<ADDITIONAL_METADATA>')[0].strip()
                                    chat_turns.append(f"Anderson: {clean_c}")
                                elif tp == 'PLANNER_RESPONSE' and isinstance(c, str) and c.strip():
                                    lines_resp = [l.strip() for l in c.strip().splitlines() if l.strip()]
                                    short_resp = " ".join(lines_resp[:3])[:250]
                                    chat_turns.append(f"Assistente: {short_resp}")
                            except:
                                pass
                        
                        recent_summary = "\n".join(chat_turns[-6:])
                        block = f"--- CHAT ANTIGRAVITY #{idx+1} (ID: {cid[:8]}... | Atualizado: {dt_str}) ---"
                        if active_doc:
                            block += f"\nArquivo em Foco: {os.path.basename(active_doc)}"
                        block += f"\nDiálogo Recente:\n{recent_summary}"
                        context_blocks.append(block)
                    except Exception as e:
                        pass
            except Exception as e:
                print(f"[Brain] Aviso ao buscar chats Antigravity: {e}")

        # 2. Codex IDE: Descobre comando / workspace ativo
        if os.path.exists(self.codex_proc_file):
            try:
                with open(self.codex_proc_file, 'r', encoding='utf-8', errors='ignore') as f:
                    procs = json.load(f)
                    if procs and isinstance(procs, list):
                        last_p = procs[-1]
                        cwd = last_p.get('cwd', '')
                        cmd = last_p.get('command', '')[:100]
                        cid = last_p.get('conversationId', '')
                        block = f"--- CHAT CODEX ATIVO (ID: {cid[:8]}...) ---\nDiretório: {cwd}\nÚltimo Comando: {cmd}"
                        context_blocks.append(block)
            except Exception as e:
                pass

        if not context_blocks:
            return "Sem contexto de chats ativos no momento."
        
        return "\n\n".join(context_blocks)

    def save_voice_history(self, target, prompt, ans):
        import datetime
        import json
        now = datetime.datetime.now()
        dt_str = now.strftime('%Y-%m-%d %H:%M:%S')
        date_str = now.strftime('%Y-%m-%d')
        
        entry_md = f"### 🎙️ [{dt_str}] {target.upper()}\n- **Anderson:** {prompt}\n- **{target.capitalize()}:** {ans}\n\n"
        
        # 1. Arquivo local Markdown legível em J:\pilula_voz\historico_voz.md
        try:
            with open(r"J:\pilula_voz\historico_voz.md", "a", encoding="utf-8") as f:
                f.write(entry_md)
        except Exception as e:
            pass

        # 2. Arquivo estruturado JSONL em J:\pilula_voz\historico_voz.jsonl
        try:
            entry_json = json.dumps({
                "timestamp": dt_str,
                "target": target,
                "user": prompt,
                "assistant": ans
            }, ensure_ascii=False) + "\n"
            with open(r"J:\pilula_voz\historico_voz.jsonl", "a", encoding="utf-8") as f:
                f.write(entry_json)
        except Exception as e:
            pass

        # 3. Arquivo no vault do Obsidian (diário de voz)
        obs_dir = r"G:\Protegido\Aplicações e Sites\Obsidian\01-HERMES-AGENT-DESKTOP\VOICE-MODE-HERMES"
        if os.path.exists(obs_dir):
            try:
                obs_md = os.path.join(obs_dir, f"historico_voz_{date_str}.md")
                if not os.path.exists(obs_md):
                    with open(obs_md, "w", encoding="utf-8") as f:
                        f.write(f"# 🎙️ Histórico de Voz — {date_str}\n\n")
                with open(obs_md, "a", encoding="utf-8") as f:
                    f.write(entry_md)
            except Exception as e:
                pass

    def generate_response(self, target, prompt):
        sys_prompt = self.router.get_system_prompt(target)
        ide_context = self.get_ide_context()
        
        # 1. Instrucoes de sistema + Contexto da IDE
        contents = [{
            "role": "user",
            "parts": [{"text": f"[INSTRUÇÃO DO SISTEMA]: {sys_prompt}\n\n[CONTEXTO COMPARTILHADO DA SESSÃO IDE ATUAL]:\n{ide_context}"}]
        }, {
            "role": "model",
            "parts": [{"text": "Entendido. Tenho o contexto da IDE."}]
        }]
        
        # 2. Historico Local (Memoria da Pilula de Voz)
        for turn in self.router.history[target][-10:]: # Ultimos 10 turnos de voz
            contents.append({"role": "user", "parts": [{"text": turn["user"]}]})
            contents.append({"role": "model", "parts": [{"text": turn["assistant"]}]})
            
        # 3. Prompt Atual
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        models_to_try = ["gemini-flash-lite-latest", "gemini-3.6-flash"]
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GOOGLE_API_KEY}"
            try:
                t0 = time.time()
                resp = requests.post(
                    url,
                    json={
                        "contents": contents,
                        "generationConfig": {
                            "temperature": 0.7,
                            "maxOutputTokens": 180
                        }
                    },
                    timeout=7
                )
                if resp.status_code == 200:
                    data = resp.json()
                    ans = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    ans = re.sub(r'[\*\#\_\[\]\`]', '', ans)
                    self.router.history[target].append({"user": prompt, "assistant": ans})
                    self.save_voice_history(target, prompt, ans)
                    print(f"[{target.upper()}] Brain ({model}) em {time.time()-t0:.2f}s: {ans}")
                    return ans
            except Exception as e:
                print(f"Brain erro no modelo {model}: {e}")
                continue

        name = "Hermes" if target == "hermes" else ("Codex" if target == "codex" else "Antigravity")
        return f"{name} aqui. Não consegui processar agora."

# ─────────────────────────────────────────────────────────────────────────────
# 4. Mouth Engine (Cartesia Sonic 2 Streaming + Auto-Failover Keys & Fallbacks)
# ─────────────────────────────────────────────────────────────────────────────
class MouthEngine:
    def __init__(self):
        self.is_playing = False
        self.is_muted = False
        self.speaker_idx = find_speaker_device()
        self.cartesia_keys = list(CARTESIA_API_KEYS)
        self.active_key_idx = 0
        self.kokoro = None

        # Vozes Cartesia
        self.cartesia_voices = {
            "hermes": CARTESIA_VOICE_ID,      # Rafael (Português Brasileiro dinâmico)
            "antigravity": CARTESIA_VOICE_ID, # Rafael
            "codex": CARTESIA_VOICE_ID        # Rafael
        }

        # Fallback remoto (Edge-TTS)
        self.edge_voices = {
            "hermes": "pt-BR-AntonioNeural",
            "antigravity": "pt-BR-FranciscaNeural",
            "codex": "pt-BR-FabioNeural"
        }

        # Fallback local (Kokoro-82M)
        self.kokoro_voices = {
            "hermes": "pm_alex",
            "antigravity": "pm_alex",
            "codex": "pm_santa"
        }

        total_keys = len(self.cartesia_keys)
        cur_k = self.cartesia_keys[self.active_key_idx][-6:] if self.cartesia_keys else "none"
        print(f"[MOUTH] Cartesia Sonic 2 ativo com {total_keys} chaves em pool (Chave atual: ...{cur_k} | Voz: Rafael | Saída: [{self.speaker_idx}]).")

        # Inicializa Kokoro em thread separada para NÃO atrasar a abertura da janela Tkinter
        def _load_kokoro_bg():
            if os.path.exists(KOKORO_ONNX_PATH) and os.path.exists(KOKORO_VOICES_PATH):
                try:
                    self.kokoro = Kokoro(KOKORO_ONNX_PATH, KOKORO_VOICES_PATH)
                except Exception:
                    self.kokoro = None
        threading.Thread(target=_load_kokoro_bg, daemon=True).start()

    def stop(self):
        self.is_playing = False
        try:
            sd.stop()
        except Exception:
            pass

    def clean_text_for_speech(self, text):
        t = re.sub(r'[*#_<>[\]`]', '', text)
        t = re.sub(r'https?://\S+', '', t)
        t = re.sub(r'[\U00010000-\U0010ffff]', '', t)
        return t.strip()

    def speak_cartesia(self, text, voice_id=CARTESIA_VOICE_ID):
        if not self.cartesia_keys or not self.is_playing:
            return False

        attempts = 0
        total_keys = len(self.cartesia_keys)

        # Loop de failover entre as chaves cadastradas
        while attempts < total_keys and self.is_playing:
            current_key = self.cartesia_keys[self.active_key_idx]
            key_tag = f"...{current_key[-6:]}"
            t0 = time.time()
            print(f"[MOUTH] Sintetizando via Cartesia Sonic 2 (Chave: {key_tag} [{self.active_key_idx+1}/{total_keys}] | Voz: Rafael)...")
            url = "https://api.cartesia.ai/tts/bytes"
            headers = {
                "X-API-Key": current_key,
                "Cartesia-Version": "2024-06-10",
                "Content-Type": "application/json"
            }
            payload = {
                "model_id": CARTESIA_MODEL_ID,
                "transcript": text,
                "voice": {
                    "mode": "id",
                    "id": voice_id
                },
                "output_format": {
                    "container": "raw",
                    "encoding": "pcm_s16le",
                    "sample_rate": 24000
                },
                "language": "pt"
            }
            try:
                r = requests.post(url, headers=headers, json=payload, stream=True, timeout=8)
                if r.status_code == 200:
                    first_chunk = True
                    buf = b""
                    with sd.OutputStream(samplerate=24000, channels=1, dtype='int16', device=self.speaker_idx) as stream:
                        for chunk in r.iter_content(chunk_size=4096):
                            if not self.is_playing:
                                break # Barge-in: usuário falou, interrompe na hora
                            if not chunk:
                                continue
                            if first_chunk:
                                print(f"[MOUTH] Primeiro som tocando em {time.time()-t0:.2f}s! (Cartesia Sonic 2)")
                                first_chunk = False
                            buf += chunk
                            n_samples = len(buf) // 2
                            if n_samples > 0:
                                pcm_bytes = buf[:n_samples * 2]
                                buf = buf[n_samples * 2:]
                                pcm_arr = np.frombuffer(pcm_bytes, dtype=np.int16)
                                stream.write(pcm_arr)
                    return True
                else:
                    print(f"[MOUTH] Cartesia erro HTTP {r.status_code} na chave {key_tag}: {r.text[:100]}")
                    # Rotaciona para a próxima chave automaticamente
                    old_idx = self.active_key_idx
                    self.active_key_idx = (self.active_key_idx + 1) % total_keys
                    next_tag = f"...{self.cartesia_keys[self.active_key_idx][-6:]}"
                    print(f"[FAILOVER CARTESIA] Chave {key_tag} indisponível. Migrando automaticamente para chave {next_tag}!")
                    attempts += 1
            except Exception as e:
                print(f"[MOUTH] Erro de rede na chave {key_tag} ({e})")
                self.active_key_idx = (self.active_key_idx + 1) % total_keys
                attempts += 1

        print("[MOUTH] Todas as chaves do Cartesia falharam. Acionando fallback Edge-TTS...")
        return False

    def speak_edge(self, text, voice="pt-BR-AntonioNeural"):
        t0 = time.time()
        print(f"[MOUTH] Sintetizando com Edge-TTS ({voice})...")

        async def _synth():
            communicate = edge_tts.Communicate(text, voice=voice, rate="+5%")
            mp3_buf = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_buf += chunk["data"]
            return mp3_buf

        try:
            mp3_data = asyncio.run(_synth())
            if not mp3_data or not self.is_playing:
                return False

            container = av.open(io.BytesIO(mp3_data))
            frames = []
            sample_rate = 24000
            for frame in container.decode(audio=0):
                sample_rate = frame.sample_rate
                arr = frame.to_ndarray()
                if arr.ndim == 2:
                    arr = arr.T
                frames.append(arr)

            if not frames or not self.is_playing:
                return False

            pcm_data = np.concatenate(frames, axis=0)
            dur = len(pcm_data) / sample_rate
            print(f"[MOUTH] Áudio pronto em {time.time()-t0:.2f}s ({dur:.1f}s de duração). Reproduzindo...")

            sd.play(pcm_data, samplerate=sample_rate, device=self.speaker_idx)
            sd.wait()
            return True
        except Exception as e:
            print(f"[MOUTH] Erro no Edge-TTS: {e}")
            return False

    def speak_kokoro(self, text, voice="pm_alex"):
        if not self.kokoro or not self.is_playing:
            return False
        t0 = time.time()
        print(f"[MOUTH] Sintetizando com Kokoro-82M local (Voz: {voice})...")
        try:
            samples, sample_rate = self.kokoro.create(text, voice=voice, speed=1.05, lang="pt-br")
            if not self.is_playing:
                return False
            gen_time = time.time() - t0
            duration = len(samples) / sample_rate
            print(f"[MOUTH] Áudio Kokoro pronto em {gen_time:.2f}s ({duration:.1f}s de duração). Reproduzindo...")
            sd.play(samples, samplerate=sample_rate, device=self.speaker_idx)
            sd.wait()
            return True
        except Exception as e:
            print(f"[MOUTH] Erro na síntese Kokoro: {e}")
            return False

    def speak(self, text, target="antigravity", on_finish=None):
        if self.is_muted or not text:
            if on_finish:
                on_finish()
            return

        self.is_playing = True
        cleaned = self.clean_text_for_speech(text)
        if not cleaned:
            self.is_playing = False
            if on_finish:
                on_finish()
            return

        c_voice = self.cartesia_voices.get(target, CARTESIA_VOICE_ID)
        e_voice = self.edge_voices.get(target, "pt-BR-AntonioNeural")
        k_voice = self.kokoro_voices.get(target, "pm_alex")

        try:
            played = False
            # 1. Cartesia Sonic 2 Streaming (com pool de chaves e rotação automática)
            if self.cartesia_keys:
                played = self.speak_cartesia(cleaned, voice_id=c_voice)

            # 2. Fallback para Edge-TTS se todas as chaves Cartesia esgotarem
            if not played and self.is_playing:
                print("[MOUTH] Fallback para Edge-TTS acionado...")
                played = self.speak_edge(cleaned, voice=e_voice)

            # 3. Fallback para Kokoro local
            if not played and self.is_playing and self.kokoro:
                print("[MOUTH] Fallback para Kokoro acionado...")
                self.speak_kokoro(cleaned, voice=k_voice)
        except Exception as e:
            print(f"[MOUTH] Falha geral de reprodução: {e}")
        finally:
            # Cooldown acústico: aguarda o som da sala se dissipar para evitar que o microfone ouça as caixas de som
            time.sleep(0.40)
            self.is_playing = False
            if on_finish:
                on_finish()

# ─────────────────────────────────────────────────────────────────────────────
# 5. Ear Engine (Deepgram Flux WebSocket with Anti-Echo & Anti-Spam)
# ─────────────────────────────────────────────────────────────────────────────
class EarEngine:
    def __init__(self, ui_queue, on_turn_complete, on_start_of_turn, mouth):
        self.ui_queue = ui_queue
        self.on_turn_complete = on_turn_complete
        self.on_start_of_turn = on_start_of_turn
        self.mouth = mouth
        self.is_listening = True
        self.is_muted = False
        self.loop = None
        self.audio_queue = asyncio.Queue(maxsize=100)
        self.last_transcript = ""
        self.last_turn_time = 0.0

    def audio_callback(self, indata, frames, time_info, status):
        if not self.is_listening or self.is_muted or not self.loop or not self.loop.is_running():
            return

        peak = np.max(np.abs(indata))

        # While assistant is speaking, only send audio if user speaks with sufficient volume (barge-in)
        if self.mouth.is_playing:
            return  # Muta o microfone completamente enquanto o assistente fala para evitar loop/eco das caixas de som

        if peak > 800 and not self.mouth.is_playing:
            self.ui_queue.put(("state", "listening"))

        raw_bytes = bytes(indata)
        try:
            self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, raw_bytes)
        except Exception:
            pass

    async def run_client(self):
        uri = "wss://api.deepgram.com/v2/listen?model=flux-general-multi&language_hint=pt&encoding=linear16&sample_rate=16000"
        headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}

        while self.is_listening:
            try:
                # Clear stale audio before connecting
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                    except Exception:
                        break

                self.ui_queue.put(("state", "idle"))
                async with websockets.connect(uri, additional_headers=headers) as ws:
                    print("[EAR] Conectado ao Deepgram Flux!")

                    async def sender():
                        try:
                            while self.is_listening:
                                chunk = await self.audio_queue.get()
                                await ws.send(chunk)
                        except asyncio.CancelledError:
                            pass
                        except Exception:
                            pass

                    async def receiver():
                        current_turn_transcript = ""
                        try:
                            async for raw_msg in ws:
                                try:
                                    msg = json.loads(raw_msg)
                                    event = msg.get("event")
                                    mtype = msg.get("type")

                                    # Visual feedback on StartOfTurn
                                    if event == "StartOfTurn" or (mtype == "TurnInfo" and event == "StartOfTurn"):
                                        current_turn_transcript = ""
                                        if not self.mouth.is_playing:
                                            self.ui_queue.put(("state", "listening"))

                                    # Transcript updates
                                    transcript = msg.get("transcript", "").strip()
                                    if not transcript and "channel" in msg:
                                        alts = msg["channel"].get("alternatives", [])
                                        if alts:
                                            transcript = alts[0].get("transcript", "").strip()

                                    if event == "Update" and transcript:
                                        current_turn_transcript = transcript

                                    # Deepgram Flux emits EndOfTurn on completion!
                                    if event in ("EndOfTurn", "TurnComplete"):
                                        final_transcript = transcript or current_turn_transcript
                                        now = time.time()
                                        if final_transcript and len(final_transcript) >= 2:
                                            # Debounce duplicate within 1.8s
                                            if final_transcript == self.last_transcript and (now - self.last_turn_time) < 1.8:
                                                print(f"[EAR] Descartando disparo duplicado de: '{final_transcript}'")
                                                continue

                                            self.last_transcript = final_transcript
                                            self.last_turn_time = now
                                            print(f"[EAR] Turno Finalizado (EndOfTurn): '{final_transcript}'")
                                            self.ui_queue.put(("state", "thinking"))
                                            self.on_turn_complete(final_transcript)
                                except Exception as e:
                                    print(f"[EAR] Erro no receiver: {e}")
                        except asyncio.CancelledError:
                            pass
                        except Exception:
                            pass

                    t_send = asyncio.create_task(sender())
                    t_recv = asyncio.create_task(receiver())

                    done, pending = await asyncio.wait(
                        [t_send, t_recv],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for t in pending:
                        t.cancel()

                    print("[EAR] Conexão finalizada normalmente. Reconectando...")

            except Exception as e:
                print(f"[EAR] Reconectando em 1s: {e}")
                await asyncio.sleep(1)

    def start(self):
        def thread_worker():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            mic_idx = find_microphone_device()
            self.stream = sd.InputStream(
                device=mic_idx,
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=self.audio_callback
            )
            with self.stream:
                self.loop.run_until_complete(self.run_client())

        t = threading.Thread(target=thread_worker, daemon=True)
        t.start()

# ─────────────────────────────────────────────────────────────────────────────
# 6. High-Fidelity 70% Compact Scale Canvas UI (450 x 64)
# ─────────────────────────────────────────────────────────────────────────────
class VoicePillUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Floating Voice Pill")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self.trans_color = "#000001"
        self.root.wm_attributes("-transparentcolor", self.trans_color)
        self.root.configure(bg=self.trans_color)

        # 70% Scale dimensions: 450 x 64
        self.W = 450
        self.H = 64
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = (screen_w - self.W) // 2
        pos_y = screen_h - self.H - 50
        self.root.geometry(f"{self.W}x{self.H}+{pos_x}+{pos_y}")

        self.ui_queue = queue.Queue()
        self.state = "idle"  # idle, listening, thinking, speaking
        self.target = "antigravity"  # hermes, antigravity, codex
        self.mic_muted = False
        self.spk_muted = False
        self._drag_data = {"x": 0, "y": 0}
        self.is_processing = False

        # Subsystems
        self.router = VoiceRouter()
        self.brain = BrainEngine(self.router)
        self.mouth = MouthEngine()
        self.ear = EarEngine(
            self.ui_queue,
            on_turn_complete=self.handle_turn_complete,
            on_start_of_turn=self.handle_barge_in,
            mouth=self.mouth
        )

        # Main Canvas
        self.canvas = tk.Canvas(
            self.root,
            width=self.W,
            height=self.H,
            bg=self.trans_color,
            bd=0,
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)

        self.ear.start()
        self.redraw()
        self.process_queue()

        self.startup_greeting()

    def startup_greeting(self):
        def greet():
            time.sleep(0.8)
            self.mouth.speak("Pronto. Pode falar comigo.", target=self.target)
        threading.Thread(target=greet, daemon=True).start()

    def render_image(self):
        scale = 3
        w, h = self.W * scale, self.H * scale
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        try:
            font_label = ImageFont.truetype("segoeuib.ttf", int(8.5 * scale))
            font_active = ImageFont.truetype("segoeuib.ttf", int(9.5 * scale))
        except Exception:
            font_label = font_active = ImageFont.load_default()

        targets = {
            "hermes": {"center_x": 160 * scale, "w": 80 * scale, "label": "HERMES"},
            "antigravity": {"center_x": 242 * scale, "w": 96 * scale, "label": "ANTIGRAVITY"},
            "codex": {"center_x": 324 * scale, "w": 80 * scale, "label": "CODEX"}
        }
        act = targets.get(self.target, targets["antigravity"])
        acx = act["center_x"]

        # 1. Outer Dark Pill with organic contour
        cy1, cy2 = 6 * scale, (h - 6 * scale)
        radius = (cy2 - cy1) // 2
        bulge_r = int(38 * scale)

        draw.ellipse([acx - bulge_r, 1 * scale, acx + bulge_r, 34 * scale], fill=(18, 20, 24, 252))
        draw.ellipse([acx - bulge_r, h - 34 * scale, acx + bulge_r, h - 1 * scale], fill=(18, 20, 24, 252))
        draw.rounded_rectangle([3 * scale, cy1, w - 3 * scale, cy2], radius=radius, fill=(18, 20, 24, 252))

        # Borders
        draw.rounded_rectangle([3 * scale, cy1, w - 3 * scale, cy2], radius=radius, outline=(45, 48, 58, 255), width=int(1.5 * scale))
        draw.arc([acx - bulge_r, 1 * scale, acx + bulge_r, 34 * scale], start=185, end=355, fill=(45, 48, 58, 255), width=int(1.5 * scale))
        draw.arc([acx - bulge_r, h - 34 * scale, acx + bulge_r, h - 1 * scale], start=5, end=175, fill=(45, 48, 58, 255), width=int(1.5 * scale))

        draw.ellipse([acx - bulge_r + 2*scale, 3 * scale, acx + bulge_r - 2*scale, 32 * scale], fill=(18, 20, 24, 252))
        draw.ellipse([acx - bulge_r + 2*scale, h - 32 * scale, acx + bulge_r - 2*scale, h - 3 * scale], fill=(18, 20, 24, 252))

        # 2. Separators
        seps = [60 * scale, 112 * scale, 370 * scale]
        for sx in seps:
            draw.line([(sx, 18 * scale), (sx, h - 18 * scale)], fill=(255, 255, 255, 26), width=scale)

        # 3. Left: Pencil / Edit Icon (Center x=31, y=32)
        px, py = 31 * scale, 32 * scale
        s = int(8 * scale)
        draw.rounded_rectangle([px - s, py - s, px + s, py + s], radius=int(2.5*scale), outline=(225, 230, 240, 240), width=int(1.5*scale))
        draw.line([(px - 2*scale, py + 2*scale), (px + 4*scale, py - 4*scale)], fill=(225, 230, 240, 240), width=int(1.8*scale))
        draw.line([(px - 3*scale, py + 3*scale), (px - 1*scale, py + 3*scale)], fill=(225, 230, 240, 240), width=int(1.8*scale))

        # 4. Microphone Icon (Center x=86, y=32)
        mx, my = 86 * scale, 32 * scale
        mic_col = (239, 68, 68, 255) if self.mic_muted else ((96, 165, 250, 255) if self.state == "listening" else (225, 230, 240, 240))
        cw, ch = int(3.5 * scale), int(6.5 * scale)
        draw.rounded_rectangle([mx - cw, my - ch - 1*scale, mx + cw, my + ch - 3*scale], radius=cw, fill=mic_col if self.state == "listening" else None, outline=mic_col, width=int(1.5*scale))
        draw.arc([mx - cw - 2*scale, my - ch + 2*scale, mx + cw + 2*scale, my + ch + 2*scale], start=0, end=180, fill=mic_col, width=int(1.5*scale))
        draw.line([(mx, my + ch + 2*scale), (mx, my + ch + 6*scale)], fill=mic_col, width=int(1.5*scale))
        draw.line([(mx - 4*scale, my + ch + 6*scale), (mx + 4*scale, my + ch + 6*scale)], fill=mic_col, width=int(1.5*scale))
        if self.mic_muted:
            draw.line([(mx - 7*scale, my - 7*scale), (mx + 7*scale, my + 7*scale)], fill=(239, 68, 68, 255), width=int(1.8*scale))

        # 5. Center: Segmented Multi-Agent Track
        track_x1, track_x2 = 120 * scale, 362 * scale
        track_y1, track_y2 = 15 * scale, h - 15 * scale
        track_r = (track_y2 - track_y1) // 2

        track_bg = (175, 202, 242, 170)
        draw.rounded_rectangle([track_x1, track_y1, track_x2, track_y2], radius=track_r, fill=track_bg)

        # Inactive labels
        for key, info in targets.items():
            if key != self.target:
                lbl = info["label"]
                bbox = font_label.getbbox(lbl)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                draw.text((info["center_x"] - tw // 2, 32 * scale - th // 2 - 1*scale), lbl, fill=(28, 42, 65, 230), font=font_label)

        # Active Luminous Floating Disc
        aw = act["w"]
        ay1 = 8 * scale
        ay2 = h - 8 * scale
        disc_h = ay2 - ay1
        ar = disc_h // 2

        disc_img = Image.new("RGBA", (aw, disc_h), (0, 0, 0, 0))
        disc_draw = ImageDraw.Draw(disc_img)

        for row in range(disc_h):
            prog = row / float(disc_h)
            r_val = int(242 * (1 - prog) + 165 * prog)
            g_val = int(248 * (1 - prog) + 205 * prog)
            b_val = int(255 * (1 - prog) + 252 * prog)
            disc_draw.line([(0, row), (aw, row)], fill=(r_val, g_val, b_val, 255))

        mask = Image.new("L", (aw, disc_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, aw - 1, disc_h - 1], radius=ar, fill=255)

        for g_pad, g_alpha in [(5*scale, 25), (3*scale, 45), (1*scale, 70)]:
            draw.rounded_rectangle([acx - aw//2 - g_pad, ay1 - g_pad, acx + aw//2 + g_pad, ay2 + g_pad], radius=ar + g_pad, fill=(90, 150, 240, g_alpha))

        img.paste(disc_img, (acx - aw//2, ay1), mask)
        draw.rounded_rectangle([acx - aw//2, ay1, acx + aw//2, ay2], radius=ar, outline=(255, 255, 255, 230), width=int(1.5*scale))

        lbl = act["label"]
        bbox = font_active.getbbox(lbl)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((acx - tw // 2, 32 * scale - th // 2 - int(2*scale)), lbl, fill=(15, 23, 42, 255), font=font_active)

        cy = ay2 - int(6 * scale)
        draw.line([(acx - 3*scale, cy - 2*scale), (acx, cy + 1*scale)], fill=(71, 85, 105, 210), width=int(1.5*scale))
        draw.line([(acx, cy + 1*scale), (acx + 3*scale, cy - 2*scale)], fill=(71, 85, 105, 210), width=int(1.5*scale))

        # 6. Speaker Icon (Center x=394, y=32)
        spx, spy = 394 * scale, 32 * scale
        spk_col = (239, 68, 68, 255) if self.spk_muted else ((96, 165, 250, 255) if self.state == "speaking" else (225, 230, 240, 240))
        draw.polygon([
            (spx - 7*scale, spy - 3*scale),
            (spx - 3*scale, spy - 3*scale),
            (spx + 2*scale, spy - 8*scale),
            (spx + 2*scale, spy + 8*scale),
            (spx - 3*scale, spy + 3*scale),
            (spx - 7*scale, spy + 3*scale)
        ], fill=spk_col if self.state == "speaking" else None, outline=spk_col, width=int(1.5*scale))
        if not self.spk_muted:
            draw.arc([spx + 3*scale, spy - 5*scale, spx + 9*scale, spy + 5*scale], start=-60, end=60, fill=spk_col, width=int(1.5*scale))
            draw.arc([spx + 5*scale, spy - 9*scale, spx + 14*scale, spy + 9*scale], start=-60, end=60, fill=spk_col, width=int(1.5*scale))
        else:
            draw.line([(spx - 8*scale, spy - 8*scale), (spx + 8*scale, spy + 8*scale)], fill=(239, 68, 68, 255), width=int(1.8*scale))

        # 7. Close button (Center x=430, y=32)
        cx, cy = 430 * scale, 32 * scale
        draw.line([(cx - 3*scale, cy - 3*scale), (cx + 3*scale, cy + 3*scale)], fill=(120, 130, 150, 180), width=int(1.5*scale))
        draw.line([(cx - 3*scale, cy + 3*scale), (cx + 3*scale, cy - 3*scale)], fill=(120, 130, 150, 180), width=int(1.5*scale))

        final_img = img.resize((self.W, self.H), Image.Resampling.LANCZOS)
        return final_img

    def redraw(self):
        self.tk_img = ImageTk.PhotoImage(self.render_image())
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

    def on_click(self, event):
        x = event.x
        self._drag_data["x"] = event.x_root - self.root.winfo_x()
        self._drag_data["y"] = event.y_root - self.root.winfo_y()

        # 70% Scale click boundaries
        # 1. Pencil (0 to 60)
        if 0 <= x < 60:
            self.new_conversation()
            return

        # 2. Mic Mute (60 to 112)
        if 60 <= x < 112:
            self.toggle_mic()
            return

        # 3. Track (112 to 370)
        if 112 <= x < 201:
            self.set_target("hermes")
            return
        elif 201 <= x < 283:
            self.set_target("antigravity")
            return
        elif 283 <= x < 370:
            self.set_target("codex")
            return

        # 4. Speaker Mute (370 to 412)
        if 370 <= x < 412:
            self.toggle_spk()
            return

        # 5. Close Button (412 to 450)
        if 412 <= x <= 450:
            self.close()
            return

    def on_drag(self, event):
        new_x = event.x_root - self._drag_data["x"]
        new_y = event.y_root - self._drag_data["y"]
        self.root.geometry(f"+{new_x}+{new_y}")

    def set_target(self, new_target):
        if self.target != new_target:
            self.target = new_target
            self.router.active_target = new_target
            print(f"[PILL] Destino alterado para: {new_target.upper()}")
            self.redraw()

    def new_conversation(self):
        self.router.history["hermes"].clear()
        self.router.history["antigravity"].clear()
        self.router.history["codex"].clear()
        print("[PILL] Nova conversa iniciada! Memória limpa.")
        self.redraw()
        def speak_greet():
            self.mouth.speak("Nova conversa iniciada.", target=self.target)
        threading.Thread(target=speak_greet, daemon=True).start()

    def toggle_mic(self):
        self.mic_muted = not self.mic_muted
        self.ear.is_muted = self.mic_muted
        self.redraw()

    def toggle_spk(self):
        self.spk_muted = not self.spk_muted
        self.mouth.is_muted = self.spk_muted
        self.redraw()

    def handle_barge_in(self):
        if self.mouth.is_playing:
            print("[BARGE-IN] Interrompendo áudio imediatamente!")
            self.mouth.stop()
            self.ui_queue.put(("state", "listening"))

    def handle_turn_complete(self, transcript):
        if self.is_processing:
            print(f"[QUEUE] Ignorando sobreposição enquanto processa: '{transcript}'")
            return

        cmd_clean = re.sub(r'[^\w\s]', '', transcript.lower()).strip()
        if cmd_clean in ["nova conversa", "novo chat", "reiniciar conversa", "limpar conversa", "comecar do zero",
                         "hermes nova conversa", "antigravity nova conversa", "codex nova conversa"]:
            self.new_conversation()
            return

        self.is_processing = True

        def brain_worker():
            try:
                target, prompt = self.router.route(transcript)
                self.ui_queue.put(("set_target", target))
                self.ui_queue.put(("state", "thinking"))

                ans = self.brain.generate_response(target, prompt)

                self.ui_queue.put(("state", "speaking"))

                def on_tts_finish():
                    self.ui_queue.put(("state", "idle"))
                    self.is_processing = False

                self.mouth.speak(ans, target=target, on_finish=on_tts_finish)
            except Exception as e:
                print(f"[BRAIN] Erro no brain_worker: {e}")
                self.is_processing = False
                self.ui_queue.put(("state", "idle"))

        threading.Thread(target=brain_worker, daemon=True).start()

    def process_queue(self):
        need_redraw = False
        try:
            while True:
                item = self.ui_queue.get_nowait()
                cmd, val = item
                if cmd == "state":
                    if self.state != val:
                        self.state = val
                        need_redraw = True
                elif cmd == "set_target":
                    if self.target != val:
                        self.target = val
                        self.router.active_target = val
                        need_redraw = True
        except queue.Empty:
            pass

        if need_redraw:
            self.redraw()
        self.root.after(40, self.process_queue)

    def close(self):
        print("[PILL] Fechando aplicação...")
        self.ear.is_listening = False
        self.mouth.stop()
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    print("Iniciando Voice Pill 70% (Hermes, Antigravity, Codex)...")
    app = VoicePillUI()
    app.run()


