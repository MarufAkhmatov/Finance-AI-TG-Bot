"""
Ovozni matniga aylantirish — faster-whisper (lokal, tekin)
"""
import os
import logging
import tempfile

log = logging.getLogger(__name__)

_model = None

def _get_model():
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
            log.info("Loading Whisper base model...")
            _model = WhisperModel("base", device="cpu", compute_type="int8")
            log.info("Whisper model loaded.")
        except ImportError:
            log.warning("faster-whisper not installed, voice disabled")
    return _model


def transcribe(audio_path: str) -> str:
    model = _get_model()
    if model is None:
        return ""
    try:
        segments, info = model.transcribe(audio_path, beam_size=3)
        text = " ".join(s.text for s in segments).strip()
        log.info("Transcribed (%s): %s", info.language, text)
        return text
    except Exception as e:
        log.error("Transcription error: %s", e)
        return ""


async def transcribe_telegram_voice(bot, file_id: str) -> str:
    """Download voice file from Telegram and transcribe."""
    tg_file = await bot.get_file(file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await tg_file.download_to_drive(tmp.name)
        path = tmp.name
    try:
        return transcribe(path)
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass
