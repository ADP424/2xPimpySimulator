from __future__ import annotations

from sqlalchemy.dialects.postgresql import ENUM

SEX = ENUM("female", "male", name="sex", create_type=True)
