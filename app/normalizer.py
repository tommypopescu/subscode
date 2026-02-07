# -*- coding: utf-8 -*-
import unicodedata

# Mapare sedilă -> virgulă (corect română):
# Ş/ş (U+015E/U+015F), Ţ/ţ (U+0162/U+0163) -> Ș/ș (U+0218/U+0219), Ț/ț (U+021A/U+021B)
MAP = {
    "\u015E": "\u0218",  # Ş -> Ș
    "\u015F": "\u0219",  # ş -> ș
    "\u0162": "\u021A",  # Ţ -> Ț
    "\u0163": "\u021B",  # ţ -> ț
}

def normalize_romanian(text: str, nfc: bool = True) -> str:
    # 1) corectează sedila la virgulă pentru S/T (istoric necesar în română)
    for src, dst in MAP.items():
        text = text.replace(src, dst)
    # 2) normalizează Unicode NFC (asigură forme precompuse pentru ă/Ă/â/Â/î/Î etc.)
    return unicodedata.normalize("NFC", text) if nfc else text
