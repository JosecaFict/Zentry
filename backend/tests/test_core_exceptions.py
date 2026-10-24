import json

import pytest
from starlette.requests import Request

from app.core.exceptions import unhandled_exception_handler


@pytest.mark.asyncio
async def test_unhandled_exception_does_not_expose_internal_details() -> None:
    request = Request({"type": "http", "method": "POST", "path": "/login", "headers": []})
    response = await unhandled_exception_handler(
        request,
        RuntimeError("password=secret database.internal:5432"),
    )

    payload = json.loads(response.body)
    assert response.status_code == 500
    assert payload == {"detail": "Ocurrió un error interno. Intenta nuevamente en unos minutos."}
    assert "secret" not in response.body.decode()
