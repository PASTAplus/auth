import daiquiri
import fastapi

import pasta_crypto
import pasta_token as pasta_token_
from config import Config
import starlette.responses
import starlette.requests

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()
