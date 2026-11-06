import pytest
from app import service
from app.llm import LLMResponseError
from app.schemas import ProductCard, ProductInput


def _fake_raw():
    return {
        "seo_title": "Манометр DM 02 Манотомь 0-1.6 МПа",
        "seo_description": "x" * 850,
        "key_features": ["Диапазон: 0-1.6 МПа", "Класс точности: 1,5"],
        "search_queries": ["манометр dm 02", "манометр 0-1.6 МПа", "манометр Манотомь"],
        "commercial_block": "Подходит для систем с давлением до 1.6 МПа.",
        "missing_fields": [],
        "notes": "",
    }


def test_detect_missing_manufacturer_none():
    p = ProductInput(name="X", manufacturer=None)
    assert "manufacturer" in service.detect_missing(p)


def test_detect_missing_empty_spec():
    p = ProductInput(name="X", manufacturer="Y", specs={"диапазон": ""})
    assert "specs.диапазон" in service.detect_missing(p)


def test_detect_missing_nested():
    p = ProductInput(name="X", foo=[], bar={"baz": {}})
    missing = service.detect_missing(p)
    assert "foo" in missing
    assert "bar.baz" in missing


def test_normalize_features_basic():
    raw = [
        "specs.диапазон: 0-1.6 МПа",
        "name: X",
        "manufacturer: Y",
        "description: d",
        "specs: z",
        "foo: bar",
        "foo: bar",
    ]
    assert service._normalize_features(raw) == ["диапазон: 0-1.6 МПа", "foo: bar"]


def test_normalize_features_no_value():
    raw = ["specs.foo"]
    assert service._normalize_features(raw) == ["foo"]


def test_merge_missing_discards_unknown():
    assert service._merge_missing(["a", "b"], ["b", "c", "a"]) == ["a", "b"]


def test_merge_missing_sorted():
    assert service._merge_missing(["b", "a"], ["a"]) == ["a", "b"]


def test_ensure_missing_features_specs():
    features = []
    assert service._ensure_missing_features(features, ["specs.x"]) == ["x: данных нет"]


def test_ensure_missing_features_metadata_no_add():
    features = []
    assert service._ensure_missing_features(features, ["name", "manufacturer"]) == []


def test_ensure_missing_features_no_duplicate():
    features = ["x: данных нет"]
    result = service._ensure_missing_features(features, ["specs.x"])
    assert result.count("x: данных нет") == 1


@pytest.mark.asyncio
async def test_generate_card_valid(monkeypatch):
    calls = {"n": 0}

    async def fake(system, user, temperature=0.3):
        calls["n"] += 1
        return _fake_raw()

    monkeypatch.setattr("app.service.chat_json", fake)
    product = ProductInput(
        name="Манометр",
        manufacturer="Манотомь",
        specs={"диапазон": "0-1.6 МПа"},
        description="desc",
    )
    card = await service.generate_card(product)
    assert isinstance(card, ProductCard)
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_generate_card_retry(monkeypatch):
    calls = {"n": 0}
    captured = {"user": ""}

    async def fake(system, user, temperature=0.3):
        calls["n"] += 1
        if calls["n"] == 1:
            raw = _fake_raw()
            raw["seo_description"] = "x" * 1400
            return raw
        captured["user"] = user
        return _fake_raw()

    monkeypatch.setattr("app.service.chat_json", fake)
    product = ProductInput(
        name="Манометр",
        manufacturer="Манотомь",
        specs={"диапазон": "0-1.6 МПа"},
        description="desc",
    )
    await service.generate_card(product)
    assert calls["n"] == 2
    assert "сократи на ~" in captured["user"]
    assert "Перепиши ТОЛЬКО проблемные поля" in captured["user"]


@pytest.mark.asyncio
async def test_generate_card_both_invalid(monkeypatch):
    async def fake(system, user, temperature=0.3):
        raw = _fake_raw()
        raw["seo_description"] = "x" * 1400
        return raw

    monkeypatch.setattr("app.service.chat_json", fake)
    product = ProductInput(
        name="Манометр",
        manufacturer="Манотомь",
        specs={"диапазон": "0-1.6 МПа"},
        description="desc",
    )
    with pytest.raises(service.GenerationError):
        await service.generate_card(product)


@pytest.mark.asyncio
async def test_generate_card_llm_response_error(monkeypatch):
    async def fake(system, user, temperature=0.3):
        raise LLMResponseError("bad json")

    monkeypatch.setattr("app.service.chat_json", fake)
    product = ProductInput(
        name="Манометр",
        manufacturer="Манотомь",
        specs={"диапазон": "0-1.6 МПа"},
        description="desc",
    )
    with pytest.raises(service.GenerationError):
        await service.generate_card(product)
