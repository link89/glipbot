from ringcentral.sdk import SDK

from .. import config
from ..utils.clients import RcPlatformHelper


class GlipService(object):

    def __init__(self, rc_platform):
        self._rc_helper = RcPlatformHelper(rc_platform)

    def login(self, username, code, redirect_uri):
        self._rc_helper.platform.login(username=username, code=code, redirect_uri=redirect_uri)

    def subscribe_webhook(self, address, event_filters=None, expires_in=50000000):
        self._rc_helper.subscribe_webhook(address=address, event_filters=event_filters, expires_in=expires_in)


_sdk = SDK(key=config.RC_KEY,
           secret=config.RC_SECRET,
           server=config.RC_SERVER,
           )
_platform = _sdk.platform()
service = GlipService(_platform)
