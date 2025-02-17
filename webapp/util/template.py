import starlette.templating

import util.utils
from config import Config

# Templates

templates = starlette.templating.Jinja2Templates(Config.TEMPLATES_PATH)
templates.env.globals.update(
    {
        # Make the url() function available in all templates
        'url': util.utils.url,
        # Parameters for base.html
        'dev_menu': Config.ENABLE_DEV_MENU,
    }
)


