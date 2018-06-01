import abc
import os
import re
import pickle

from typing import Sequence, Optional

from ringcentral.sdk import SDK

from .. import config
from ..utils.clients import RcPlatformHelper, FeedHelper
from ..db.dao import Dao

import logging
logger = logging.getLogger(__name__)


class BaseCmd(abc.ABC):

    @abc.abstractmethod
    def parse(self, post) -> Optional[tuple]:
        ...

    @abc.abstractmethod
    async def run(self, post, *args):
        ...


class SubscribeCmd(BaseCmd):
    pattern = re.compile(r"^rss subscribe ([^ ]+)")

    def __init__(self, dao: Dao, rc_helper: RcPlatformHelper, feed_helper: FeedHelper):
        self.dao = dao
        self.rc_helper = rc_helper
        self.feed_helper = feed_helper

    def parse(self, post):
        match = self.pattern.match(post["body"]["text"] or "")
        if match is not None:
            return match.groups()

    async def run(self, post, url):
        group_id = post["body"]["groupId"]
        raw_feed = await self._fetch_feed(group_id, url)
        href = raw_feed.get("href", url)
        self._create_subscription(group_id, href)

    async def _fetch_feed(self, group_id, url):
        try:
            res = await self.feed_helper.get_feed(url)
            feed = self.feed_helper.parse(res.body)
        except Exception as e:
            self.rc_helper.post_to_group(group_id, "fail to create fetch feed from {}".format(url))
            raise e
        else:
            return feed

    def _create_subscription(self, group_id, href):
        feed = self.dao.get_or_create_feed(href)
        subscription = self.dao.get_subscription(group_id, feed.id)
        if subscription is not None:
            self.rc_helper.post_to_group(group_id, "you have already subscribed this feed {}".format(href))
        else:
            self.dao.get_or_create_subscription(group_id, feed.id)
            self.rc_helper.post_to_group(group_id, "successfully subscribe feed {}".format(href))


class GlipService(object):
    def __init__(self, rc_helper, cmd_services: Sequence[BaseCmd]):
        self.rc_helper = rc_helper
        self.cmd_services = cmd_services

    def login(self, username, extension, code, redirect_uri):
        self.rc_helper.platform.login(username=username, extension=extension, code=code, redirect_uri=redirect_uri)
        with open(config.RC_AUTH_TOKEN_CACHE, mode='wb') as f:
            auth = self.rc_helper.platform.auth()
            pickle.dump(auth, f)

    def subscribe_webhook(self, address, event_filters=None, expires_in=50000000):
        self.rc_helper.subscribe_webhook(address=address, event_filters=event_filters, expires_in=expires_in)

    async def dispatch(self, post):
        creator_id = post["body"]["creatorId"]
        if creator_id == self.rc_helper.me["id"]:
            return None
        for cmd_service in self.cmd_services:
            logger.info("try command service: %s", cmd_service)
            match = cmd_service.parse(post)
            if match is not None:
                logger.info("command service: %s is match the command pattern", cmd_service)
                await cmd_service.run(post, *match)
                break
        else:
            self.rc_helper.post_to_group(post["body"]["groupId"], post["body"]["text"])


# Dao
_dao = Dao()


# ringcentral platform
_sdk = SDK(key=config.RC_KEY,
           secret=config.RC_SECRET,
           server=config.RC_SERVER,
           )
_platform = _sdk.platform()
if os.path.exists(config.RC_AUTH_TOKEN_CACHE):
    with open(config.RC_AUTH_TOKEN_CACHE, mode='rb') as f:
        _platform._auth = pickle.load(f)
_rc_helper = RcPlatformHelper(_platform)

# rss feed
_feed_helper = FeedHelper()


# cmd services
cmd_services = (
    SubscribeCmd(dao=_dao, rc_helper=_rc_helper, feed_helper=_feed_helper),
)


# glip service
service = GlipService(rc_helper=_rc_helper, cmd_services=cmd_services)
