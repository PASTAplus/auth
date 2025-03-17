import daiquiri
import fastapi

import util.redirect

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


@router.get('/')
async def index():
    return util.redirect.internal('/ui/profile')
