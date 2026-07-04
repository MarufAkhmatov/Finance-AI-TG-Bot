"""
Chek rasmidan matn o'qish — Tesseract OCR
"""
import os
import logging
import tempfile

log = logging.getLogger(__name__)

TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_receipt_text(image_path: str) -> str:
    try:
        import pytesseract
        from PIL import Image
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang="rus+eng")
        return text.strip()
    except Exception as e:
        log.error("OCR error: %s", e)
        return ""


async def ocr_telegram_photo(bot, file_id: str) -> str:
    tg_file = await bot.get_file(file_id)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        await tg_file.download_to_drive(tmp.name)
        path = tmp.name
    try:
        return extract_receipt_text(path)
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass
