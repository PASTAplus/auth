import fastapi
import starlette.requests
import starlette.responses

router = fastapi.APIRouter()


@router.get('/v1/ping')
async def ping():
    return starlette.responses.Response(
        content='pong',
    )
