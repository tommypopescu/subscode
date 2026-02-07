FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# rulează ca user neprivilegiat (bună practică de securitate)
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
RUN chown -R appuser:appuser /app
USER appuser

# Defaults (NFC activat implicit)
ENV WATCH_MODE=watch \
    SCAN_INTERVAL_S=600 \
    FILE_EXTS="srt,ass,ssa,vtt,sub,txt" \
    WATCH_PATHS="/sources" \
    BACKUP_DIR="/backup" \
    BACKUP_ORIGINAL=true \
    BACKUP_CONVERTED=true \
    NORMALIZE_RO=true \
    NORMALIZE_NFC=true \
    REMOVE_BOM=true

VOLUME ["/sources", "/backup"]
ENTRYPOINT ["python", "-m", "app.main"]
