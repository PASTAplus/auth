import fastapi
import starlette.requests
import starlette.responses

router = fastapi.APIRouter()


@router.get('/auth/ping')
async def ping():
    return starlette.responses.Response(
        content='pong',
    )

