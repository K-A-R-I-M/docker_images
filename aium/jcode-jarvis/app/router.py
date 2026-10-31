"""Local intents that do not need the cloud brain."""
from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.store import Store

class Route:
    def __init__(self, reply: str | None = None, action: str = "", lang: str = "en"):
        self.reply = reply
        self.action = action
        self.lang = lang


class Router:
    """Small local intents. Everything else goes to the brain."""

    def route(self, text: str, lang: str, store: Store) -> Route:
        # Order matters: stop and goodbye must win over greetings and memory verbs.
        raw = text.strip()
        low = raw.lower()

        if re.search(r"\b(stop|pause|silence|tais[- ]toi|arrête|arrete)\b", low):
            return Route("D'accord, j'arrête." if lang == "fr" else "Okay, stopping.", "stop", lang)

        if re.search(r"\b(goodbye|bye|au revoir|à plus|a plus)\b", low):
            return Route("Au revoir." if lang == "fr" else "Goodbye.", "end", lang)

        remember = re.match(
            r"^(?:please\s+)?(?:remember(?:\s+that)?|retiens(?:\s+que)?|souviens[- ]toi(?:\s+que)?)\s+(.+)$",
            raw,
            re.IGNORECASE,
        )
        if remember:
            fact = remember.group(1).strip()
            store.remember(fact)
            reply = "Je m'en souviendrai." if lang == "fr" else "I'll remember that."
            return Route(reply, "", lang)

        forget = re.match(
            r"^(?:please\s+)?(?:forget(?:\s+that)?|oublie)\s+(.+)$",
            raw,
            re.IGNORECASE,
        )
        if forget:
            count = store.forget(forget.group(1))
            if count:
                reply = "J'ai oublié ça." if lang == "fr" else "I forgot that."
            else:
                reply = "Je n'ai rien trouvé à oublier." if lang == "fr" else "I didn't find that to forget."
            return Route(reply, "", lang)

        if re.search(r"\b(what do you remember|what do you know|qu'est[- ]ce que tu (?:sais|te rappelles)|tu te rappelles quoi)\b", low):
            facts = store.recall("", 5)
            if facts:
                joined = "; ".join(fact["text"] for fact in facts)
                reply = "Je me souviens de ceci : " + joined if lang == "fr" else "I remember this: " + joined
            else:
                reply = "Je n'ai rien en mémoire pour l'instant." if lang == "fr" else "I don't have anything in memory yet."
            return Route(reply, "", lang)

        if re.search(r"\b(what time|quelle heure|the time)\b", low):
            now = datetime.now()
            if lang == "fr":
                reply = f"Il est {now.hour} h {now.minute:02d}."
            else:
                reply = now.strftime("It's %I:%M %p.").replace(" 0", " ")
            return Route(reply, "", lang)

        if re.search(r"\b(what date|what day|quelle date|quel jour)\b", low):
            now = datetime.now()
            if lang == "fr":
                reply = f"Nous sommes le {now.day} {now.strftime('%B %Y')}."
            else:
                reply = now.strftime("Today is %A, %d %B %Y.")
            return Route(reply, "", lang)

        if re.match(r"^(hi|hello|hey|bonjour|salut|bonsoir)[.!]?$", low):
            return Route("Bonjour. Je t'écoute." if lang == "fr" else "Hi. I'm listening.", "", lang)

        return Route(None, "", lang)


