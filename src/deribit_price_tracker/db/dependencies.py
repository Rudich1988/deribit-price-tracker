from typing import Annotated

from fastapi import Depends, Request

from deribit_price_tracker.db.database import Database


def get_database(request: Request) -> Database:
    return request.app.state.database


DatabaseDep = Annotated[Database, Depends(get_database)]
