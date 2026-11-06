from __future__ import annotations

METADATA_FIELDS = frozenset({"name", "manufacturer", "description", "specs"})
SPECS_PREFIX = "specs."


def is_metadata_label(label: str) -> bool:
    """Метаданные для нормализованных меток key_features (без префикса specs.)."""
    return label in METADATA_FIELDS


def is_metadata_path(path: str) -> bool:
    """Метаданные для путей missing_fields (только сами корневые поля)."""
    return path in METADATA_FIELDS


def feature_label(path: str) -> str:
    """Нормализует путь к виду, который ждём в key_features (снимает specs.)."""
    return path.removeprefix(SPECS_PREFIX).strip()
