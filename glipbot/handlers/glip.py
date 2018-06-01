import json
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
        glip.service.login(username=config.RC_BOT_NUMBER,
                           extension=config.RC_BOT_EXTENSION,
                           code=code,
                           redirect_uri=config.RC_AUTH_REDIRECT_URI,
                           )
        self.finish()


class GlipEventsHandler(BaseHandler):
    VERIFICATION_TOKEN_HEADER = "Verification-Token"
    VALIDATION_TOKEN_HEADER = "Validation-Token"

    async def post(self, *args, **kwargs):
        verification_token = self.request.headers.get(self.VERIFICATION_TOKEN_HEADER)
        if verification_token != config.RC_WEBHOOK_TOKEN:
            return self.send_error(401)
        validation_token = self.request.headers.get(self.VALIDATION_TOKEN_HEADER)
        if validation_token is not None:
            self.set_header(self.VALIDATION_TOKEN_HEADER, validation_token)
        self.finish()
        logger.info("body is: %s", self.request.body)
        if self.request.body:
            glip.service.dispatch(json.loads(self.request.body))
