import pytest
from pydantic import ValidationError

from app.schemas import ProductCard, ProductInput


def test_product_input_extra_allow():
    p = ProductInput(name="X", foo="bar")
    assert p.foo == "bar"


def test_product_input_trims_strings_and_keys():
    p = ProductInput(name="  X  ", specs={" a ": " b "})
    assert p.name == "X"
    assert p.specs == {"a": "b"}


def test_product_input_none_and_empty_preserved():
    p = ProductInput(name="", manufacturer=None)
    assert p.name == ""
    assert p.manufacturer is None


def test_product_card_empty_title():
    with pytest.raises(ValidationError):
        ProductCard(
            seo_title="",
            seo_description="x" * 800,
            search_queries=["q1", "q2", "q3"],
            commercial_block="block",
        )


def test_product_card_title_too_long():
    with pytest.raises(ValidationError):
        ProductCard(
            seo_title="x" * 71,
            seo_description="x" * 800,
            search_queries=["q1", "q2", "q3"],
            commercial_block="block",
        )


def test_product_card_desc_range():
    with pytest.raises(ValidationError):
        ProductCard(
            seo_title="t",
            seo_description="x" * 799,
            search_queries=["q1", "q2", "q3"],
            commercial_block="block",
        )
    with pytest.raises(ValidationError):
        ProductCard(
            seo_title="t",
            seo_description="x" * 1201,
            search_queries=["q1", "q2", "q3"],
            commercial_block="block",
        )
    ProductCard(
        seo_title="t",
        seo_description="x" * 800,
        search_queries=["q1", "q2", "q3"],
        commercial_block="block",
    )
    ProductCard(
        seo_title="t",
        seo_description="x" * 1200,
        search_queries=["q1", "q2", "q3"],
        commercial_block="block",
    )


def test_product_card_search_queries_count():
    with pytest.raises(ValidationError):
        ProductCard(
            seo_title="t",
            seo_description="x" * 800,
            search_queries=["q1", "q2"],
            commercial_block="block",
        )
    with pytest.raises(ValidationError):
        ProductCard(
            seo_title="t",
            seo_description="x" * 800,
            search_queries=["q1", "q2", "q3", "q4", "q5", "q6"],
            commercial_block="block",
        )
    for n in (3, 4, 5):
        ProductCard(
            seo_title="t",
            seo_description="x" * 800,
            search_queries=["q"] * n,
            commercial_block="block",
        )
