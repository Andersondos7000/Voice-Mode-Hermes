"""Checks against the installed Hermes runtime; synthetic audio is explicitly labelled."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

RUNTIME = Path(r"C:\Users\Anderson\AppData\Local\hermes\hermes-agent")
PROFILE = Path(r"C:\Users\Anderson\AppData\Local\hermes\profiles\voice-mode-hermes")
os.environ["HERMES_HOME"] = str(PROFILE)
sys.path.insert(0, str(RUNTIME))
OUT = PROFILE / "cache" / "audio" / "validacao-voz-20260912"
OUT.mkdir(parents=True, exist_ok=True)


def save(data):
    path = OUT / "resultado.json"
    latest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    latest.update(data)
    path.write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["tts", "stt", "agent", "playback", "mic", "device", "cancel"])
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--model")
    args = parser.parse_args()
    report_path = OUT / "resultado.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    start = time.monotonic()
    result = {"success": False}
    try:
        if args.stage == "tts":
            from tools.tts_tool import text_to_speech_tool
            text = "Olá, Hermes. Quanto é dois mais três? Responda em português com uma frase curta."
            raw = json.loads(text_to_speech_tool(text, output_path=str(OUT / "entrada-sintetica.mp3")))
            result = {k: raw.get(k) for k in ("success", "provider", "file_path")}
            result["synthetic_input"] = True
        elif args.stage == "stt":
            from tools.voice_mode import transcribe_recording
            from tools.transcription_tools import _get_provider, _load_stt_config
            path = report["tts"].get("file_path")
            raw = transcribe_recording(path)
            result = {k: raw.get(k) for k in ("success", "provider", "transcript")}
            result["resolved_provider"] = _get_provider(_load_stt_config())
            result["synthetic_input"] = True
        elif args.stage == "agent":
            prompt = report["stt"].get("transcript")
            if not prompt:
                raise RuntimeError("STT did not produce a transcript")
            command = [str(RUNTIME / "venv" / "Scripts" / "hermes.exe"), "-p", "voice-mode-hermes",
                       "-t", "clarify", "-z", prompt]
            if args.model:
                command.extend(["--model", args.model])
            proc = subprocess.run(
                command,
                cwd=OUT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
            )
            response = proc.stdout.strip()
            import re
            expected = bool(re.search(r"\bcinco\b|\b5\b", response, re.I))
            is_error = bool(re.search(r"^HTTP\s+[45]\d\d|^Error:|^Erro:", response, re.I))
            result = {"success": proc.returncode == 0 and expected and not is_error,
                      "exit_code": proc.returncode, "expected_answer_verified": expected and not is_error,
                      "agent_seconds": round(time.monotonic()-start, 2)}
            if result["success"]:
                result["response"] = response
                from tools.tts_tool import text_to_speech_tool
                spoken = json.loads(text_to_speech_tool(response, output_path=str(OUT / "resposta.mp3")))
                result["tts_success"] = spoken.get("success", False)
                result["file_path"] = spoken.get("file_path")
                result["success"] = bool(result["tts_success"])
            else:
                # No raw stderr: provider diagnostics can contain credentials.
                result["diagnostic"] = "Agent command failed; inspect sanitized diagnostics locally"
        elif args.stage == "playback":
            from tools.voice_mode import play_audio_file
            result = {"success": play_audio_file(report["agent"]["file_path"]), "human_hearing_confirmed": False}
        elif args.stage == "device":
            import sounddevice as sd
            captured = []
            def count_frames(indata, frames, timing, status):
                captured.append(frames)
            with sd.InputStream(channels=1, samplerate=16000, dtype="int16", callback=count_frames):
                time.sleep(1)
            result = {"success": sum(captured) > 0, "captured_frames": sum(captured),
                      "input_device": sd.query_devices(None, "input")["name"],
                      "human_speech_validated": False, "audio_retained": False}
        elif args.stage == "mic":
            import numpy as np
            from tools.voice_mode import create_audio_recorder, transcribe_recording
            rec = create_audio_recorder()
            try:
                print("MIC_RECORDING_STARTED", flush=True)
                rec.start()
                time.sleep(args.seconds)
                wav_path = rec.stop()
                if not wav_path:
                    raise RuntimeError("No microphone frames captured")
                import wave
                with wave.open(wav_path) as wav:
                    samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
                    duration = wav.getnframes() / wav.getframerate()
                raw = transcribe_recording(wav_path)
                result = {"success": raw.get("success", False), "transcript": raw.get("transcript", ""),
                          "duration_seconds": round(duration, 2), "rms": round(float(np.sqrt(np.mean(samples.astype(float)**2))), 2)}
                Path(wav_path).unlink(missing_ok=True)
            finally:
                rec.shutdown()
        elif args.stage == "cancel":
            import threading
            import tools.voice_mode as voice_mode
            from tools.voice_mode import play_audio_file, stop_playback
            thread = threading.Thread(target=play_audio_file, args=(report["tts"]["file_path"],))
            thread.start()
            deadline = time.monotonic() + 10
            while voice_mode._active_playback is None and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.02)
            if voice_mode._active_playback is None:
                thread.join(timeout=10)
                raise RuntimeError("Player did not enter a cancellable state")
            time.sleep(0.2)
            cancelled = time.monotonic()
            stop_playback()
            thread.join(timeout=3)
            result = {"success": not thread.is_alive(), "stop_seconds": round(time.monotonic()-cancelled, 3),
                      "automatic_cancel": True, "barge_in_validated": False}
    except Exception as exc:
        result = {"success": False, "error_type": type(exc).__name__}
    result["seconds"] = round(time.monotonic() - start, 2)
    report[args.stage] = result
    save({args.stage: result})
    print(json.dumps({args.stage: result}, ensure_ascii=False), flush=True)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
