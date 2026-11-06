from __future__ import annotations

from app.schemas import ProductCard, ProductInput


def to_markdown(card: ProductCard, product: ProductInput) -> str:
    """Формирует Markdown-представление карточки товара."""
    lines = []
    name = getattr(product, "name", None)
    manufacturer = getattr(product, "manufacturer", None)
    name = "" if name is None else str(name).strip()
    manufacturer = "" if manufacturer is None else str(manufacturer).strip()
    lines.append(f"# {name or 'Товар'}")
    lines.append(f"**Производитель:** {manufacturer or 'не указан'}")
    lines.append("")
    lines.append(f"## SEO-заголовок\n{card.seo_title}")
    lines.append("")
    lines.append(f"## SEO-описание\n{card.seo_description}")
    lines.append("")
    lines.append("## Ключевые характеристики")
    for feature in card.key_features:
        lines.append(f"- {feature}")
    lines.append("")
    lines.append("## Поисковые запросы")
    for query in card.search_queries:
        lines.append(f"- {query}")
    lines.append("")
    lines.append("## Commercial-блок")
    lines.append(card.commercial_block)
    if card.missing_fields:
        lines.append("")
        lines.append("## Отсутствующие/неполные поля")
        for field in card.missing_fields:
            lines.append(f"- {field}")
    if card.notes:
        lines.append("")
        lines.append(f"## Примечания\n{card.notes}")
    return "\n".join(lines) + "\n"
