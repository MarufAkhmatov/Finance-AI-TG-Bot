FROM python:3.11-slim

# System deps: Tesseract OCR + curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download cloudflared binary
RUN curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Override run_bot.py to use Linux cloudflared path
ENV CF_BIN=cloudflared
ENV TESSERACT_CMD=/usr/bin/tesseract

EXPOSE 8900

CMD ["python", "run_bot.py"]
