import abc
import os
import re
import pickle

from ringcentral.sdk import SDK

from .. import config
from ..utils.clients import RcPlatformHelper, FeedHelper
from ..db.schemas import Session
from ..db.schemas import (
    Feed,
    Entry,
)

import logging
logger = logging.getLogger(__name__)


class GlipService(object):
    def __init__(self, rc_platform):
        self.rc_helper = RcPlatformHelper(rc_platform)

    def login(self, username, extension, code, redirect_uri):
        self.rc_helper.platform.login(username=username, extension=extension, code=code, redirect_uri=redirect_uri)
        with open(config.RC_AUTH_TOKEN_CACHE, mode='wb') as f:
            auth = self.rc_helper.platform.auth()
            pickle.dump(auth, f)

    def subscribe_webhook(self, address, event_filters=None, expires_in=50000000):
        self.rc_helper.subscribe_webhook(address=address, event_filters=event_filters, expires_in=expires_in)

    def dispatch(self, post):
        creator_id = post["body"]["creatorId"]
        if creator_id == self.rc_helper.me["id"]:
            return None
        self.rc_helper.post_to_group(post["body"]["groupId"], post["body"]["text"])



class BaseCmd(abc.ABC):

    @abc.abstractmethod
    def parse(self, post):
        ...

    @abc.abstractmethod
    async def run(self, post, *args):
        ...


class SubscribeCmd(BaseCmd):
    pattern = re.compile(r"^rss subscribe ([^ ]+)")

    def __init__(self, rc_helper, feed_helper):
        self.rc_helper: RcPlatformHelper = rc_helper
        self.feed_helper: FeedHelper = feed_helper

    def parse(self, post):
        match = self.pattern.match(post["body"]["test"] or "")
        if match is not None:
            return match.groups()

    async def run(self, post, url):
        group_id = post["body"]["groupId"]
        feed = await self._fetch_feed(group_id, url)

    async def _fetch_feed(self, group_id, url):
        try:
            res = await self.feed_helper.get_feed(url)
            feed = self.feed_helper.parse(res.body)
        except Exception as e:
            self.rc_helper.post_to_group(group_id, "fail to create a subscription to {}".format(url))
            raise e
        else:
            return feed



# ringcentral platform
_sdk = SDK(key=config.RC_KEY,
           secret=config.RC_SECRET,
           server=config.RC_SERVER,
           )
_platform = _sdk.platform()
if os.path.exists(config.RC_AUTH_TOKEN_CACHE):
    with open(config.RC_AUTH_TOKEN_CACHE, mode='rb') as f:
        _platform._auth = pickle.load(f)

# rss feed

_feed_helper = FeedHelper()


service = GlipService(_platform)
