from __future__ import annotations

from typing import Optional

# Stat buckets are calibrated against the average stat value of 10.
_STAT_LABELS: tuple[tuple[int, str], ...] = (
    (4, "Very Low"),
    (7, "Low"),
    (9, "Slightly Low"),
    (10, "Average"),
    (12, "Slightly High"),
    (15, "High"),
    (10**9, "Very High"),
)


def stat_label(value: Optional[int]) -> str:
    """
    Return a qualitative label for a numeric stat value.

    Examples
    --------
    ``stat_label(3)`` → "Very Low"
    ``stat_label(10)`` → "Average"
    ``stat_label(20)`` → "Very High"
    """
    if value is None:
        return "Unknown"
    v = int(value)
    for threshold, label in _STAT_LABELS:
        if v <= threshold:
            return label
    return "Very High"


# Health is a simple bucket on an absolute scale. Base is 10.
_HEALTH_LABELS: tuple[tuple[int, str], ...] = (
    (0, "Dead"),
    (2, "Critical"),
    (4, "Badly Wounded"),
    (6, "Injured"),
    (8, "Bruised"),
    (10, "Healthy"),
    (10**9, "Robust"),
)


def health_label(value: Optional[int]) -> str:
    if value is None:
        return "Unknown"
    v = int(value)
    for threshold, label in _HEALTH_LABELS:
        if v <= threshold:
            return label
    return "Robust"


def messiness_label(messiness: int) -> str:
    """
    Describe kennel mess without exposing raw numbers.

    The scale is the same for every kennel size: "Spotless" means `messiness == 0`,
    "Disgusting" starts at 15 (roughly 1.5 days of unchecked mess in a full 10-pooch kennel)
    and "Biohazard" means the kennel has hit KENNEL_MAX_MESSINESS and can't get any worse.
    """
    from ..constants import KENNEL_MAX_MESSINESS

    if messiness <= 0:
        return "Spotless"
    if messiness < 3:
        return "Mostly Clean"
    if messiness < 8:
        return "Messy"
    if messiness < 15:
        return "Very Messy"
    if messiness < KENNEL_MAX_MESSINESS:
        return "Disgusting"
    return "Biohazard"


# Starvation counter → label. 0 is "Well-fed", rising from there.
_STARVATION_LABELS: tuple[tuple[int, str], ...] = (
    (0, "Well-fed"),
    (5, "Peckish"),
    (12, "Hungry"),
    (24, "Famished"),
    (48, "Starving"),
    (10**9, "Dying of Hunger"),
)


def starvation_label(starvation: Optional[int]) -> str:
    if starvation is None or starvation <= 0:
        return "Well-fed"
    v = int(starvation)
    for threshold, label in _STARVATION_LABELS:
        if v <= threshold:
            return label
    return "Dying of Hunger"


def size_label(size: Optional[int]) -> str:
    """Rough weight-class label for player-facing display. Size values are in kg."""
    if size is None:
        return "Unknown"
    v = int(size)
    if v <= 0:
        return "Unknown"
    if v < 5:
        return "Tiny"
    if v < 10:
        return "Small"
    if v < 20:
        return "Medium"
    if v < 35:
        return "Large"
    if v < 55:
        return "Very Large"
    return "Giant"


def mess_output_label(mess_output: Optional[int]) -> str:
    """
    Qualitative descriptor for a pooch's contribution to kennel mess.
    Used in vet exams/snapshots.
    """
    if mess_output is None:
        return "Unknown"
    v = int(mess_output)
    if v <= 1:
        return "Tidy"
    if v <= 3:
        return "Ordinary"
    if v <= 5:
        return "Messy"
    if v <= 8:
        return "Very Messy"
    return "Filthy"


def consumption_label(consumption: Optional[int]) -> str:
    """Qualitative descriptor for hourly food consumption."""
    if consumption is None:
        return "Unknown"
    v = int(consumption)
    if v <= 1:
        return "Tiny Appetite"
    if v <= 3:
        return "Light Eater"
    if v <= 5:
        return "Average Appetite"
    if v <= 8:
        return "Big Eater"
    return "Ravenous"
