"""HTTP Basic authentication and the Atlas analyst identity lookup."""

from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

basic = HTTPBasic()


def verify_identity(request: Request, credentials: Annotated[HTTPBasicCredentials, Depends(basic)]):
    settings = request.app.state.settings
    if not settings.analyst_password or not (
        compare_digest(credentials.username.encode(), settings.analyst.encode())
        and compare_digest(credentials.password.encode(), settings.analyst_password.encode())
    ):
        raise HTTPException(401, "Sign in as the demo analyst", headers={"WWW-Authenticate": "Basic"})

    analyst = request.app.state.store.identity(settings.analyst)
    if not analyst or not analyst["active"]:
        raise HTTPException(403, "This analyst is inactive in Atlas")
    return analyst


Analyst = Annotated[dict, Depends(verify_identity)]
