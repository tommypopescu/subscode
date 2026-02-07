# -*- coding: utf-8 -*-
"""
Normalizator pentru diacriticele românești.

- Convertește variantele istorice cu sedilă (Ş/Ţ) la forma corectă cu virgulă
  dedesubt (Ș/Ț) pentru limba română.
- (Implicit) aplică normalizarea Unicode NFC pentru a stabiliza formele compuse/
  decompuse (ex.: 'a' + combining breve -> 'ă').
"""

import unicodedata

# Mapare sedilă -> virgulă (corect română):
# Ş/ş (U+015E/U+015F), Ţ/ţ (U+0162/U+0163) -> Ș/ș (U+0218/U+0219), Ț/ț (U+021A/U+021B)
_SEDILLA_TO_COMMA = {
    "\u015E": "\u0218",  # Ş -> Ș
    "\u015F": "\u0219",  # ş -> ș
    "\u0162": "\u021A",  # Ţ -> Ț
    "\u0163": "\u021B",  # ţ -> ț
}

def normalize_romanian(text: str, nfc: bool = True) -> str:
    """
    Normalizează diacriticele românești.

    1) Înlocuiește S/T cu sedilă cu forma corectă S/T cu virgulă.
    2) Dacă `nfc=True`, normalizează Unicode la NFC (forme precompuse).

    Args:
        text: conținutul sursă (str).
        nfc:  dacă se aplică unicodedata.normalize('NFC', text).

    Returns:
        Textul normalizat.
    """
    if any(ch in text for ch in _SEDILLA_TO_COMMA):
        for src, dst in _SEDILLA_TO_COMMA.items():
            text = text.replace(src, dst)
    return unicodedata.normalize("NFC", text) if nfc else text
