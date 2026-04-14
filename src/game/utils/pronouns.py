from __future__ import annotations

import re
from typing import Any, Mapping, Optional

# Map every accepted pronoun word to a tuple (male, female, neutral).
_PRONOUN_TABLE: dict[str, tuple[str, str, str]] = {
    "he": ("he", "she", "they"),
    "him": ("him", "her", "them"),
    "his": ("his", "her", "their"),
    "himself": ("himself", "herself", "themselves"),
    # Female forms — treated symmetrically so "[pooch_she]" works on male too.
    "she": ("he", "she", "they"),
    "her": ("him", "her", "them"),
    "hers": ("his", "hers", "theirs"),
    "herself": ("himself", "herself", "themselves"),
    # "they/them/their/themselves" are also accepted as neutral placeholders.
    "they": ("he", "she", "they"),
    "them": ("him", "her", "them"),
    "their": ("his", "her", "their"),
    "themselves": ("himself", "herself", "themselves"),
}


_PLACEHOLDER_RE = re.compile(r"\[([a-zA-Z_][a-zA-Z0-9_]*?)\]")


def _resolve_sex(obj: Any) -> str:
    """Return 'male', 'female', or 'neutral' from a pooch-like object."""
    if obj is None:
        return "neutral"
    sex = getattr(obj, "sex", None)
    if sex is None:
        return "neutral"
    sex = str(sex).strip().lower()
    if sex == "male":
        return "male"
    if sex == "female":
        return "female"
    return "neutral"


def _pronoun_for(word: str, sex_bucket: str) -> Optional[str]:
    """Return the appropriate pronoun form for a given lookup word + sex bucket."""
    forms = _PRONOUN_TABLE.get(word.lower())
    if forms is None:
        return None
    male, female, neutral = forms
    if sex_bucket == "male":
        return male
    if sex_bucket == "female":
        return female
    return neutral


def _apply_case(template_word: str, replacement: str) -> str:
    """
    Match the case of ``template_word`` on ``replacement``.

    - All upper → upper (``[pooch_HE]`` → "HE")
    - Title case (first letter upper, rest lower) → title (``[pooch_He]`` → "She")
    - Otherwise → lowercase
    """
    if not template_word:
        return replacement
    if template_word.isupper():
        return replacement.upper()
    if template_word[0].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement.lower()


def _get_name(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    name = getattr(obj, "name", None)
    if name is None and isinstance(obj, Mapping):
        name = obj.get("name")
    return str(name) if name is not None else None


def substitute_placeholders(template: str, refs: Mapping[str, Any] | None = None) -> str:
    """
    Substitute role-based placeholders in ``template`` using ``refs``.

    Parameters
    ----------
    template:
        The raw message string. May contain any number of placeholders.
    refs:
        Mapping from role name (e.g. ``"pooch"``, ``"victim"``) to a
        pooch-like object with ``.sex`` and ``.name`` attributes.

    Returns
    -------
    str
        ``template`` with all known placeholders replaced. Unknown
        placeholders are left untouched so failures are visible.
    """
    if not template or "[" not in template:
        return template
    refs = refs or {}

    def _replace(match: re.Match[str]) -> str:
        raw = match.group(1)

        # Bare role → name: "[pooch]" → pooch.name
        if "_" not in raw:
            role = raw.lower()
            if role in refs:
                name = _get_name(refs[role])
                if name is not None:
                    return name
            return match.group(0)

        role_part, _, tail = raw.partition("_")
        role = role_part.lower()

        # Name-style placeholder: "[pooch_name]" → pooch.name.
        if tail.lower() == "name":
            if role in refs:
                name = _get_name(refs[role])
                if name is not None:
                    return name
            return match.group(0)

        # Pronoun placeholder: "[pooch_he]" / "[pooch_He]" / "[pooch_HE]"
        if role in refs and tail.lower() in _PRONOUN_TABLE:
            sex_bucket = _resolve_sex(refs[role])
            pronoun = _pronoun_for(tail, sex_bucket)
            if pronoun is not None:
                return _apply_case(tail, pronoun)

        return match.group(0)

    return _PLACEHOLDER_RE.sub(_replace, template)
