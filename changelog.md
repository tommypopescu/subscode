## v0.2.0 — 2026-02-07
- Normalize Unicode **NFC** activat by default (stabilizează ă/Ă, â/Â, î/Î)
- Corecție istorică Ș/Ț (virgulă, nu sedilă) menținută
- Conversie atomică + backup timestamped..

Robustificare decodare:

UTF‑8 strict are prioritate (evităm stricarea fișierelor corecte).
Scor „RO” pe decodări 8‑biți (favorizează ă/Â/Î/Ș/Ț, penalizează Ã/Å/Â…).
Re‑interpretare mojibake: text.encode('cp1252'|'cp1250').decode('utf-8').
Salvare agresivă (optională) a substituțiilor uzuale: þ→ț, º→ș, ã→ă etc.



Backup în același director (implicit):

BACKUP_SAME_DIR=true
BACKUP_ORIGINAL=true → file.srt.bak.<timestamp>
BACKUP_CONVERTED=false (păstrezi doar originalul de siguranță; pune true dacă vrei și varianta convertită) → file.srt.utf8.bak.<timestamp>
BACKUP_TIMESTAMP=true → dacă pui false, vei avea un singur .bak care va fi suprascris
BACKUP_ORIG_SUFFIX=".bak", BACKUP_CONV_SUFFIX=".utf8.bak"



Altele:

WATCH_MODE=watch|scan (fallback automat la PollingObserver pentru NAS/FUSE)
SCAN_INTERVAL_S (ex. 300)
FILE_EXTS="srt,ass,ssa,vtt,sub,txt"
WATCH_PATHS="/sources,/sources/series"
