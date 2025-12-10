import daiquiri
import fastapi

import util.url

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


@router.get('/')
async def index():
    return util.url.internal('/ui/profile')
