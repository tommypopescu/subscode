# -*- coding: utf-8 -*-
import os
import time
from pathlib import Path

import chardet
from .normalizer import normalize_romanian  # import relativ: rulăm cu `python -m app.main`

# --------- Config din ENV ----------
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

# Mai multe căi, separate prin virgulă
SOURCES = [Path(p.strip()) for p in ENV("WATCH_PATHS", "/sources").split(",") if p.strip()]

# Fallback-uri uzuale (subtitrări vechi)
TRY_ENCODINGS = ["utf-8", "cp1250", "iso-8859-2", "iso-8859-16", "cp1252"]


# --------- Helperi ----------
def is_subtitle(path: Path) -> bool:
    return path.is_file() and path.suffix.lower().lstrip(".") in EXTENSIONS


def detect_encoding(data: bytes) -> str:
    """
    Folosește chardet pentru detectarea encoding-ului.
    """
    res = chardet.detect(data)  # {'encoding': 'Windows-1250', 'confidence': ...}
    enc = (res.get("encoding") or "").lower()
    return enc


def to_unicode(data: bytes) -> str:
    """
    Decodează bytes -> str încercând: chardet + fallback-uri comune.
    """
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


# --- Fix “mojibake” tipic pentru română (UTF-8 interpretat ca CP1252/CP1250) ---
MOJIBAKE_MARKERS = (
    "Ã®", "Ã¢", "Å£", "ÅŸ", "Åž", "Å¢",  # pattern-uri frecvente
    "ÃŽ", "Ã‚", "Ã„â€º", "Ã„Æ’"
)

def fix_mojibake_romanian(text: str) -> str:
    """
    Reface fișiere deja “stricate” când UTF-8 a fost citit greșit ca Windows-1252/1250.
    Heuristic: dacă găsim markeri tipici, reîncercăm decodarea inversă:
      (str greșit) -> encode('cp1252'/'cp1250') -> decode('utf-8')
    """
    if not any(m in text for m in MOJIBAKE_MARKERS):
        return text
    # Încercare cp1252 -> utf-8
    try:
        return text.encode("cp1252", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:
        pass
    # Fallback cp1250 -> utf-8
    try:
        return text.encode("cp1250", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:
        return text


def maybe_remove_bom(utf8_bytes: bytes) -> bytes:
    if utf8_bytes.startswith(b'\xef\xbb\xbf') and REMOVE_BOM:
        return utf8_bytes[3:]
    return utf8_bytes


def convert_file(path: Path):
    # Calculează relația pentru backup (păstrează structura)
    rel = None
    for base in SOURCES:
        try:
            rel = path.relative_to(base)
            break
        except ValueError:
            continue
    rel = rel or path.name

    # Timestamp UTC aware (fără DeprecationWarning)
    from datetime import datetime, UTC
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    data = path.read_bytes()
    text = to_unicode(data)

    # 1) Repară mojibake (UTF-8 -> CP1252/CP1250)
    text = fix_mojibake_romanian(text)

    # 2) Normalizare română + NFC (Ș/Ț virgulă + forme precompuse)
    if NORMALIZE_RO or NORMALIZE_NFC:
        text = normalize_romanian(text, nfc=NORMALIZE_NFC)

    out_bytes = maybe_remove_bom(text.encode("utf-8"))

    # Dacă e deja identic în UTF-8, ieșim
    if data == out_bytes or data.replace(b'\xef\xbb\xbf', b'') == out_bytes:
        return False

    # Backup original (timestamped)
    if BACKUP_ORIGINAL:
        dst = BACKUP_DIR / "original" / f"{rel}"
        dst.parent.mkdir(parents=True, exist_ok=True)
        (dst.parent / f"{Path(rel).name}.{ts}.orig").write_bytes(data)

    # Scriere atomică
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(out_bytes)
    os.replace(tmp, path)

    # Backup convertit (timestamped)
    if BACKUP_CONVERTED:
        dst2 = BACKUP_DIR / "converted" / f"{rel}.{ts}.utf8"
        dst2.parent.mkdir(parents=True, exist_ok=True)
        dst2.write_bytes(out_bytes)

    print(f"[OK] Converted to UTF-8: {path}")
    return True


def process_path(p: Path):
    if is_subtitle(p):
        try:
            convert_file(p)
        except Exception as ex:
            print(f"[ERR] {p}: {ex}")


def full_scan():
    for src in SOURCES:
        if not src.exists():
            continue
        for root, _, files in os.walk(src):
            for name in files:
                process_path(Path(root) / name)


def run_watch():
    """
    Încearcă observer inotify; dacă nu e disponibil (ex. mergerfs/NAS), cade pe PollingObserver.
    Ignoră căile inexistente.
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers.polling import PollingObserver  # fallback

        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    process_path(Path(event.src_path))
            def on_modified(self, event):
                if not event.is_directory:
                    process_path(Path(event.src_path))

        valid_sources = [p for p in SOURCES if p.exists()]
        if not valid_sources:
            print("[WARN] No valid paths. Falling back to periodic scan.")
            return run_scan()

        observer = Observer()
        for src in valid_sources:
            observer.schedule(Handler(), str(src), recursive=True)

        try:
            observer.start()
        except OSError as e:
            print(f"[WARN] inotify failed ({e}); switching to PollingObserver")
            observer = PollingObserver()
            for src in valid_sources:
                observer.schedule(Handler(), str(src), recursive=True)
            observer.start()

        print(f"[WATCH] monitoring: {', '.join(str(s) for s in valid_sources)}")
        while True:
            time.sleep(1)
    finally:
        try:
            observer.stop()
            observer.join()
        except Exception:
            pass


def run_scan():
    print(f"[SCAN] interval={SCAN_INTERVAL_S}s; paths: {', '.join(str(s) for s in SOURCES)}")
    while True:
        full_scan()
        time.sleep(SCAN_INTERVAL_S)


if __name__ == "__main__":
    # Asigură că backup path-ul există
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if WATCH_MODE.lower() == "watch":
        run_watch()
    else:
        run_scan()
