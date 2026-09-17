$voiceHermesExe = 'C:\Users\Anderson\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe'
if (-not (Test-Path -LiteralPath $voiceHermesExe)) {
    throw 'Executável instalado do Hermes não encontrado.'
}
Write-Host 'Perfil: voice-mode-hermes | Whisper local | Edge TTS pt-BR'
Write-Host 'Digite /voice on. Use Ctrl+B para iniciar/parar a gravação.'
Write-Host 'Digite /voice status para consultar e /voice off para desligar.'
Write-Host 'Este atalho usa apenas a ferramenta de esclarecimento para a conversa básica.'
& $voiceHermesExe -p voice-mode-hermes -t clarify --cli
