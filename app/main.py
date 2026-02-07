# -*- coding: utf-8 -*-
"""
Subtitle UTF-8 Fixer — scanare / watch, detectare robustă și corectare diacritice românești.
- Repară mojibake (UTF-8 citit ca CP1252/CP1250) prin re-interpretare controlată.
- Normalizează Ș/Ț (virgulă) + NFC (forme precompuse pt ă/Ă, â/Â, î/Î).
- Backup în același director prin schimbarea extensiei (implicit .bak + timestamp).
"""

import os
import time
from pathlib import Path

import chardet
from .normalizer import normalize_romanian  # rulăm cu `python -m app.main`

# ------------------ Config din ENV ------------------
ENV = lambda k, d=None: os.environ.get(k, d)

WATCH_MODE        = ENV("WATCH_MODE", "watch").strip().lower()  # watch|scan
SCAN_INTERVAL_S   = int(ENV("SCAN_INTERVAL_S", "600"))
EXTENSIONS        = set(e.lower().strip() for e in ENV("FILE_EXTS", "srt,ass,ssa,vtt,sub,txt").split(","))
# Montări de intrare (separate prin virgulă)
SOURCES           = [Path(p.strip()) for p in ENV("WATCH_PATHS", "/sources").split(",") if p.strip()]

# Control conversie & normalizare
NORMALIZE_RO      = ENV("NORMALIZE_RO", "true").lower() == "true"    # Ș/Ț virgulă
NORMALIZE_NFC     = ENV("NORMALIZE_NFC", "true").lower() == "true"   # Unicode NFC
REMOVE_BOM        = ENV("REMOVE_BOM", "true").lower() == "true"

# Politici RO & mojibake
RO_LANG           = ENV("RO_LANG", "true").lower() == "true"         # activează scorare/heuristici RO
AGGRESSIVE_SALVAGE= ENV("AGGRESSIVE_SALVAGE", "true").lower() == "true"  # înlocuiri uzuale þ/º/ã etc.

# Backup în același director
BACKUP_ORIGINAL   = ENV("BACKUP_ORIGINAL", "true").lower() == "true"
BACKUP_CONVERTED  = ENV("BACKUP_CONVERTED", "false").lower() == "true"   # implicit false ca să nu aglomerăm
BACKUP_SAME_DIR   = ENV("BACKUP_SAME_DIR", "true").lower() == "true"     # by default: în același director
BACKUP_TIMESTAMP  = ENV("BACKUP_TIMESTAMP", "true").lower() == "true"    # adaugă timestamp ca să nu suprascrii
BACKUP_ORIG_SUFFIX= ENV("BACKUP_ORIG_SUFFIX", ".bak")                    # rezultă: file.srt.bak[.ts]
BACKUP_CONV_SUFFIX= ENV("BACKUP_CONV_SUFFIX", ".utf8.bak")               # rezultă: file.srt.utf8.bak[.ts]

# Fallback-uri uzuale (subtitrări vechi)
TRY_ENCODINGS = ["utf-8", "iso-8859-16", "cp1250", "iso-8859-2", "cp1252"]

# ------------------ Helperi ------------------
def is_subtitle(path: Path) -> bool:
    return path.is_file() and path.suffix.lower().lstrip(".") in EXTENSIONS

def detect_encoding(data: bytes) -> str:
    """Detector generic (chardet)."""
    res = chardet.detect(data)  # {'encoding': 'Windows-1250', 'confidence': ...}
    return (res.get("encoding") or "").lower()

# markeri clasici mojibake UTF-8 citit ca 1252/1250
MOJIBAKE_MARKERS = ("Ã®", "Ã¢", "Å£", "ÅŸ", "Åž", "Å¢", "ÃŽ", "Ã‚", "Ã„â€º", "Ã„Æ’", "Ã„", "Â")
ROMANIAN_DIACS = set("ăâîșțĂÂÎȘȚ" + "şţŞŢ")  # includem şi formele cu sedilă (le corectăm ulterior)

def looks_like_mojibake(text: str) -> bool:
    return any(m in text for m in MOJIBAKE_MARKERS)

def ro_quality_score(text: str) -> int:
    """Punctează o decodare după cât de 'românească' arată și penalizează mojibake."""
    score = 0
    score += sum(1 for ch in text if ch in ROMANIAN_DIACS) * 3
    for m in MOJIBAKE_MARKERS:
        score -= text.count(m) * 4
    score -= text.count("\ufffd") * 5  # replacement char
    return score

def to_unicode_best(data: bytes) -> str:
    """
    1) Încearcă UTF-8 strict; dacă reușește, returnează.
    2) Încearcă encoding-uri 8-biți → alege-l pe cel cu scor 'RO' maxim.
    """
    try:
        return data.decode("utf-8")  # strict
    except UnicodeDecodeError:
        pass

    candidates = ["iso-8859-16", "cp1250", "iso-8859-2", "cp1252"]
    best_txt, best_score = None, -10**9
    for enc in candidates:
        try:
            t = data.decode(enc, errors="strict")
        except UnicodeDecodeError:
            t = data.decode(enc, errors="replace")
        s = ro_quality_score(t) if RO_LANG else 0
        if s > best_score:
            best_txt, best_score = t, s
    return best_txt if best_txt is not None else data.decode("latin-1", errors="replace")

def fix_mojibake_romanian(text: str) -> str:
    """
    Repara cazurile în care un UTF-8 a fost interpretat ca Windows-1252/1250.
    Heuristic: dacă detectăm markeri tipici, reîncercăm recodarea inversă.
    """
    if not looks_like_mojibake(text):
        return text
    # încercare cp1252 -> utf-8
    try:
        recoded = text.encode("cp1252", errors="ignore").decode("utf-8", errors="ignore")
        if looks_like_mojibake(recoded):
            recoded2 = text.encode("cp1250", errors="ignore").decode("utf-8", errors="ignore")
            if ro_quality_score(recoded2) > ro_quality_score(recoded):
                recoded = recoded2
        return recoded
    except Exception:
        try:
            return text.encode("cp1250", errors="ignore").decode("utf-8", errors="ignore")
        except Exception:
            return text

SALVAGE_MAP = {
    "þ": "ț", "Þ": "Ț",   # thorn -> t
    "º": "ș", "ª": "Ș",   # ord.masc/fem -> s
    "ã": "ă", "Ã": "Ă",   # foarte frecvent în fișiere “românizate” greșit
}

def salvage_gremlins(text: str) -> str:
    """Înlocuiri agresive pentru substituții uzuale (dezactivabil)."""
    if not (AGGRESSIVE_SALVAGE and RO_LANG):
        return text
    hits = sum(text.count(k) for k in SALVAGE_MAP.keys())
    if hits < 2:  # prag conservator
        return text
    for k, v in SALVAGE_MAP.items():
        text = text.replace(k, v)
    return text

def maybe_remove_bom(utf8_bytes: bytes) -> bytes:
    return utf8_bytes[3:] if utf8_bytes.startswith(b'\xef\xbb\xbf') and REMOVE_BOM else utf8_bytes

def write_backup_same_dir(path: Path, content: bytes, suffix: str, ts: str | None) -> None:
    """
    Scrie backup în același director:
      - <file>.srt.bak.<ts>    (pt original)
      - <file>.srt.utf8.bak.<ts> (pt convertit)
    Dacă BACKUP_TIMESTAMP=false, nu adaugă timestamp și va suprascrie.
    """
    if not BACKUP_SAME_DIR:
        return  # cerința ta: folosim același dir; altfel, nu facem nimic aici
    name = path.name  # ex: film.srt
    backup_name = name + suffix + (f".{ts}" if (BACKUP_TIMESTAMP and ts) else "")
    bpath = path.with_name(backup_name)
    try:
        bpath.write_bytes(content)
    except Exception as ex:
        print(f"[WARN] backup write failed: {bpath} ({ex})")

def convert_file(path: Path):
    # Ignoră fișiere fără extensie suportată
    if not is_subtitle(path):
        return False

    # Timestamp UTC aware
    from datetime import datetime, UTC
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    # Citește și alege decodarea “cea mai bună”
    data = path.read_bytes()
    text = to_unicode_best(data)

    # Repara mojibake (UTF-8<->CP1252/CP1250)
    text = fix_mojibake_romanian(text)

    # Salvare agresivă (þ/º/ã etc.)
    text = salvage_gremlins(text)

    # Normalizare românească + NFC (Ș/Ț virgulă + forme precompuse)
    if NORMALIZE_RO or NORMALIZE_NFC:
        text = normalize_romanian(text, nfc=NORMALIZE_NFC)

    out_bytes = maybe_remove_bom(text.encode("utf-8"))

    # Dacă rezultatul nu schimbă cu nimic fișierul existent (considerând BOM), ieșim
    if data == out_bytes or data.replace(b'\xef\xbb\xbf', b'') == out_bytes:
        return False

    # Backup original (în același director)
    if BACKUP_ORIGINAL:
        write_backup_same_dir(path, data, BACKUP_ORIG_SUFFIX, ts)

    # Scriere atomică a conversiei
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(out_bytes)
    os.replace(tmp, path)

    # (opțional) Backup și al convertitului (în același director)
    if BACKUP_CONVERTED:
        write_backup_same_dir(path, out_bytes, BACKUP_CONV_SUFFIX, ts)

    print(f"[OK] Converted to UTF-8: {path}")
    return True

def process_path(p: Path):
    try:
        if is_subtitle(p):
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
    Încearcă inotify; dacă FS nu-l suportă (NAS/FUSE/mergerfs), cade pe PollingObserver.
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
    # nu mai creăm directoare de backup — lucrăm în același director
    if WATCH_MODE == "watch":
        run_watch()
    else:
        run_scan()
