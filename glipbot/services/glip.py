import pickle
import os
from ringcentral.sdk import SDK

from .. import config
from ..utils.clients import RcPlatformHelper

import logging
logger = logging.getLogger(__name__)


class GlipService(object):
    def __init__(self, rc_platform):
        self._rc_helper = RcPlatformHelper(rc_platform)

    def login(self, username, extension, code, redirect_uri):
        self._rc_helper.platform.login(username=username, extension=extension, code=code, redirect_uri=redirect_uri)
        with open(config.RC_AUTH_TOKEN_CACHE, mode='wb') as f:
            auth = self._rc_helper.platform.auth()
            pickle.dump(auth, f)

    def subscribe_webhook(self, address, event_filters=None, expires_in=50000000):
        self._rc_helper.subscribe_webhook(address=address, event_filters=event_filters, expires_in=expires_in)

    def dispatch(self, post):
        creator_id = post["body"]["creatorId"]
        if creator_id == self._rc_helper.me["id"]:
            return None
        self._rc_helper.post_to_group(post["body"]["groupId"], post["body"]["text"])




_sdk = SDK(key=config.RC_KEY,
           secret=config.RC_SECRET,
           server=config.RC_SERVER,
           )
_platform = _sdk.platform()
if os.path.exists(config.RC_AUTH_TOKEN_CACHE):
    with open(config.RC_AUTH_TOKEN_CACHE, mode='rb') as f:
        _platform._auth = pickle.load(f)
service = GlipService(_platform)
