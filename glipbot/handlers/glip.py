from . import BaseHandler
from ..services import glip
from .. import config

import logging
logger = logging.getLogger(__name__)


class BaseGlipHandler(BaseHandler):
    ...


class GlipAuthHandler(BaseHandler):
    async def get(self, *args, **kwargs):
        code = self.get_argument('code')
        glip.service.login(username=config.RC_BOT_ACCOUNT,
                           code=code,
                           redirect_uri=config.RC_AUTH_REDIRECT_URI,
                           )
        glip.service.subscribe_webhook(address=config.RC_EVENTS_URI)
        self.finish()


class GlipEventsHandler(BaseHandler):
    async def post(self, *args, **kwargs):
        logger.info("body is: %s", self.request.body)
        self.finish()
