import starlette.templating

import db.models.profile
import util.url
from config import Config

templates = starlette.templating.Jinja2Templates(Config.TEMPLATES_PATH)
templates.env.globals.update(
    {
        # Make these functions and other objects available in all templates
        'url': util.url.url,
        'url_buster': util.url.url_buster,
        'enable_dev_menu': Config.ENABLE_DEV_MENU,
        'enable_ctrl_draw': getattr(Config, 'ENABLE_CTRL_DRAW', False),
        'IdpName': db.models.profile.IdpName,
    }
)
