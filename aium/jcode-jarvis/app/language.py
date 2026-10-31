"""Small language helpers."""
from __future__ import annotations

import re

FR_WORDS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "est", "je", "tu",
    "il", "elle", "nous", "vous", "ils", "elles", "que", "qui", "quoi", "pour",
    "avec", "dans", "sur", "pas", "ne", "ce", "cette", "mon", "ma", "mes",
    "ton", "ta", "tes", "son", "sa", "ses", "au", "aux", "en", "y", "oui",
    "non", "bonjour", "salut", "merci", "s'il", "plaît", "oublie", "retiens",
    "souviens", "heure", "date", "arrête", "au", "revoir",
}
EN_WORDS = {
    "the", "a", "an", "and", "is", "are", "i", "you", "he", "she", "we",
    "they", "that", "this", "what", "who", "why", "how", "for", "with", "in",
    "on", "not", "do", "does", "my", "your", "his", "her", "our", "their",
    "yes", "no", "hello", "hi", "thanks", "please", "remember", "forget",
    "time", "date", "stop", "goodbye", "bye",
}


def detect_lang(text: str, forced: str = "auto") -> str:
    """Return fr or en; a forced language wins, otherwise score common words."""
    forced = (forced or "auto").lower()
    if forced in ("en", "fr"):
        return forced
    low = text.lower()
    if re.search(r"[àâçéèêëîïôûùüÿœ]", low):
        return "fr"
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", low)
    if not words:
        return "en"
    fr = sum(1 for w in words if w in FR_WORDS)
    en = sum(1 for w in words if w in EN_WORDS)
    return "fr" if fr > en else "en"


_SENT_RE = re.compile(r"[^.!?…]+[.!?…]*")


