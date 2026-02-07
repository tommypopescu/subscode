# -*- coding: utf-8 -*-
import os, time
from pathlib import Path
import chardet
from .normalizer import normalize_romanian

ENV = lambda k, d=None: os.environ.get(k, d)

WATCH_MODE       = ENV("WATCH_MODE", "watch")  # watch|scan
SCAN_INTERVAL_S  = int(ENV("SCAN_INTERVAL_S", "600"))
EXTENSIONS       = set(e.lower().strip() for e in ENV("FILE_EXTS", "srt,ass,ssa,vtt,sub,txt").split(","))
BACKUP_DIR       = Path(ENV("BACKUP_DIR", "/backup"))
BACKUP_ORIGINAL  = ENV("BACKUP_ORIGINAL", "true").lower() == "true"
BACKUP_CONVERTED = ENV("BACKUP_CONVERTED", "true").lower() == "true"
NORMALIZE_RO     = ENV("NORMALIZE_RO", "true").lower() == "true"
NORMALIZE_NFC    = ENV("NORMALIZE_NFC", "true").lower() == "true"  # NFC ON by default
REMOVE_BOM       = ENV("REMOVE_BOM", "true").lower() == "true"
SOURCES          = [Path(p.strip()) for p in ENV("WATCH_PATHS", "/sources").split(",") if p.strip()]

TRY_ENCODINGS = ["utf-8", "cp1250", "iso-8859-2", "iso-8859-16", "cp1252"]

def is_subtitle(path: Path) -> bool:
    return path.is_file() and path.suffix.lower().lstrip(".") in EXTENSIONS

def detect_encoding(data: bytes) -> str:
    res = chardet.detect(data)  # {'encoding': 'Windows-1250', 'confidence': ...}
    enc = (res.get("encoding") or "").lower()
    return enc

def to_unicode(data: bytes) -> str:
    enc = detect_encoding(data)
    tried = []
    for candidate in ([enc] if enc else []) + TRY_ENCODINGS:
        if not candidate or candidate in tried:
            continue
        try:
            return data.decode(candidate)
        except Exception:
            tried.append(candidate)
    # fallback “sigur”: latin-1 cu replace
    return data.decode("latin-1", errors="replace")

def maybe_remove_bom(utf8_bytes: bytes) -> bytes:
    return utf8_bytes[3:] if utf8_bytes.startswith(b'\xef\xbb\xbf') and REMOVE_BOM else utf8_bytes

def convert_file(path: Path):
    rel = None
    for base in SOURCES:
        try:
            rel = path.relative_to(base)
            break
        except ValueError:
            continue
    rel = rel or path.name

    data = path.read_bytes()
    text = to_unicode(data)
    if NORMALIZE_RO or NORMALIZE_NFC:
        text = normalize_romanian(text, nfc=NORMALIZE_NFC)

    out_bytes = maybe_remove_bom(text.encode("utf-8"))

    # dacă deja e identic în UTF-8, ieșim
    if data == out_bytes or data.replace(b'\xef\xbb\xbf', b'') == out_bytes:
        return False

    # backup-uri cu timestamp
    from datetime import datetime
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    if BACKUP_ORIGINAL:
        dst = BACKUP_DIR / "original" / f"{rel}"
        dst.parent.mkdir(parents=True, exist_ok=True)
        (dst.parent / f"{Path(rel).name}.{ts}.orig").write_bytes(data)

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(out_bytes)
    os.replace(tmp, path)

    if BACKUP_CONVERTED:
        dst2 = BACKUP_DIR / "converted" / f"{rel}.{ts}.utf8"
        dst2.parent.mkdir(parents=True, exist_ok=True)
        dst2.write_bytes(out_bytes)

    print(f"[OK] Converted to UTF-8: {path}")
    return True

def process_path(p: Path):
    if is_subtitle(p):
        try: convert_file(p)
        except Exception as ex: print(f"[ERR] {p}: {ex}")

def full_scan():
    for src in SOURCES:
        for root, _, files in os.walk(src):
            for name in files:
                process_path(Path(root) / name)

def run_watch():
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except Exception:
        print("[WARN] watchdog indisponibil; comut pe scan periodic.")
        return run_scan()

    class Handler(FileSystemEventHandler):
        def on_created(self, event): 
            if not event.is_directory: process_path(Path(event.src_path))
        def on_modified(self, event):
            if not event.is_directory: process_path(Path(event.src_path))

    observer = Observer()
    h = Handler()
    for src in SOURCES:
        observer.schedule(h, str(src), recursive=True)
    observer.start()
    print(f"[WATCH] monitoring: {', '.join(str(s) for s in SOURCES)}")
    try:
        while True: time.sleep(1)
    finally:
        observer.stop(); observer.join()

def run_scan():
    print(f"[SCAN] interval={SCAN_INTERVAL_S}s; paths: {', '.join(str(s) for s in SOURCES)}")
    while True:
        full_scan(); time.sleep(SCAN_INTERVAL_S)

if __name__ == "__main__":
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if WATCH_MODE.lower() == "watch": run_watch()
    else: run_scan()
