from __future__ import annotations

from typing import Literal

SEO_TITLE_MAX_LENGTH = 70
SEO_DESCRIPTION_MIN_LENGTH = 800
SEO_DESCRIPTION_MAX_LENGTH = 1200


type OutputFormat = Literal["md", "json"]
OUTPUT_FORMATS: tuple[str, ...] = ("md", "json")
