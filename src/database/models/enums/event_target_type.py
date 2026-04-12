from __future__ import annotations

from types import SimpleNamespace

# Plain list of valid target type strings.
# Validation is enforced at resource-load time by the Python validator.
# The database stores target_type as TEXT.
EVENT_TARGET_TYPE = SimpleNamespace(
    enums=[
        "owner",
        "pooch",
        "kennel",
        "server",
    ]
)
