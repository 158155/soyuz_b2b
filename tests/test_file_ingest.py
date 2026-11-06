import pytest

from app.services.file_ingest import InputFileError, read_products


class FakeUpload:
    def __init__(self, data: bytes):
        self._data = data

    async def read(self):
        return self._data


@pytest.mark.asyncio
async def test_read_products_array():
    data = b'[{"name":"X","manufacturer":"Y"}]'
    products = await read_products(FakeUpload(data))
    assert len(products) == 1
    assert products[0].name == "X"


@pytest.mark.asyncio
async def test_read_products_object():
    data = b'{"name":"X"}'
    products = await read_products(FakeUpload(data))
    assert len(products) == 1
    assert products[0].name == "X"


@pytest.mark.asyncio
async def test_read_products_bad_json():
    with pytest.raises(InputFileError):
        await read_products(FakeUpload(b"{bad}"))


@pytest.mark.asyncio
async def test_read_products_not_utf8():
    with pytest.raises(InputFileError):
        await read_products(FakeUpload(b"\xff\xfe"))


@pytest.mark.asyncio
async def test_read_products_empty_array():
    with pytest.raises(InputFileError):
        await read_products(FakeUpload(b"[]"))


@pytest.mark.asyncio
async def test_read_products_invalid_field():
    with pytest.raises(InputFileError) as exc:
        await read_products(FakeUpload(b'{"name": 123}'))
    assert "название" in str(exc.value) or "name" in str(exc.value)
