import abc
import os
import re
import time
import pickle
import asyncio

import tornado.ioloop
from tornado.platform.asyncio import to_asyncio_future

from typing import Sequence, Optional

from ringcentral.sdk import SDK

from .. import config
from ..utils.clients import RcPlatformHelper, FeedHelper
from ..db.dao import Dao
from ..db.schemas import Feed, Subscription

import logging
logger = logging.getLogger(__name__)


class BaseCmd(abc.ABC):
    pattern = None

    def parse(self, post) -> Optional[tuple]:
        text = self.get_text(post).strip()
        match = self.pattern.match(text)
        if match is not None:
            return match.groups()

    @abc.abstractmethod
    async def run(self, post, *args):
        ...

    @classmethod
    def get_text(cls, post):
        return post["body"]["text"] or ""

    @classmethod
    def get_group_id(cls, post):
        return post["body"]["groupId"]


class EchoCmd(BaseCmd):
    """
    this command is for debug
    """
    pattern = re.compile(r"^echo$")

    def __init__(self, rc_helper: RcPlatformHelper):
        self.rc_helper = rc_helper

    async def run(self, post, *args):
        group_id = self.get_group_id(post)
        self.rc_helper.post_to_group(group_id, 'echo')


class RssSubscribeCmd(BaseCmd):
    """
    subscribe to rss feed
    """
    pattern = re.compile(r"^rss subscribe ([^ ]+)$")

    def __init__(self, dao: Dao, rc_helper: RcPlatformHelper, feed_helper: FeedHelper):
        self.dao = dao
        self.rc_helper = rc_helper
        self.feed_helper = feed_helper

    async def run(self, post, uri: str, *args):
        uri = uri.strip()
        group_id = self.get_group_id(post)
        raw_feed = await self._fetch_feed(group_id, uri)
        title = self.feed_helper.get_feed_title(raw_feed)
        self._create_subscription(group_id, uri, title)

    async def _fetch_feed(self, group_id, url):
        try:
            res = await self.feed_helper.get_feed(url)
            feed = self.feed_helper.parse(res.body)
        except Exception as e:
            msg = "Fail to subscribe {}, ensure the url you provide is a valid RSS feed!".format(url)
            self.rc_helper.post_to_group(group_id, msg)
            raise e
        else:
            return feed

    def _create_subscription(self, group_id, uri, title):
        feed = self.dao.update_or_create_feed(uri, title)
        subscription = self.dao.get_subscription(group_id, feed.id)
        if subscription is not None:
            msg = "You have already subscribed this feed {} !".format(uri)
            self.rc_helper.post_to_group(group_id, msg)
        else:
            # here we set last_updated to one hour before now for new subscription
            # so that the subscriber will receive the update within one hour
            last_updated = int(time.time()) - 3600
            self.dao.update_or_create_subscription(group_id, feed.id, last_updated=last_updated)
            msg = "Successfully subscribe feed {} !".format(uri)
            self.rc_helper.post_to_group(group_id, msg)


class RssListCmd(BaseCmd):
    pattern = re.compile(r"^rss list$")

    def __init__(self, dao: Dao, rc_helper: RcPlatformHelper):
        self.dao = dao
        self.rc_helper = rc_helper

    async def run(self, post, *args):
        group_id = self.get_group_id(post)
        subscriptions = self.dao.get_subscriptions(group_id=group_id, lazy=False)
        cards = []
        for subscription in subscriptions:
            card = self.rc_helper.new_simple_card(
                title=self.rc_helper.new_link(subscription.feed.title, subscription.feed.uri),
            )
            cards.append(card)
        if cards:
            text = "You have subscribed {} feeds!".format(len(cards))
            data = self.rc_helper.new_simple_cards(text=text, cards=cards)
        else:
            text = "You don't yet subscribe any feeds! Subscribe your first feed by following command: " \
                   "[code] rss subscribe uri_of_feed"
            data = self.rc_helper.new_simple_cards(text=text)
        self.rc_helper.post_to_group(group_id, data)


class GlipService(object):
    def __init__(self, dao: Dao, rc_helper: RcPlatformHelper, feed_helper: FeedHelper,
                 cmd_services: Sequence[BaseCmd],
                 fetch_period=300, push_period=300):
        self.dao = dao
        self.rc_helper = rc_helper
        self.feed_helper = feed_helper
        self.cmd_services = cmd_services
        self.fetch_period = fetch_period
        self.push_period = push_period

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

    async def update_feed(self, feed: Feed):
        logger.info("update feed: start to update %s", feed.uri)
        res = await self.feed_helper.get_feed(feed.uri)
        raw_feed = self.feed_helper.parse(res.body)
        for raw_entry in self.feed_helper.get_feed_entries(raw_feed):
            self.dao.update_or_create_entry(
                feed_id=feed.id,
                key=self.feed_helper.get_entry_key(raw_entry),
                title=self.feed_helper.get_entry_title(raw_entry),
                link=self.feed_helper.get_entry_link(raw_entry),
                summary=self.feed_helper.get_entry_summary(raw_entry),
                thumbnail=self.feed_helper.get_thumbnail(raw_entry),
                last_updated=self.feed_helper.get_entry_updated(raw_entry),
            )
        self.dao.update_or_create_feed(
            uri=feed.uri,
            title=self.feed_helper.get_feed_title(raw_feed)
        )
        logger.info("update feed: success to update %s", feed.uri)

    async def update_feeds(self):
        while True:
            logger.info("update feeds: start")
            futures = list(self.update_feed(feed) for feed in self.dao.get_feeds())
            futures.append(asyncio.sleep(self.fetch_period))
            done, pending = await asyncio.wait(futures, timeout=self.fetch_period, return_when=asyncio.ALL_COMPLETED)
            for future in pending:
                future.cancel()
            logger.info("update feeds: done")

    def update_feeds_in_background(self):
        tornado.ioloop.future_add_done_callback(to_asyncio_future(self.update_feeds()), lambda _:_)


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
    EchoCmd(rc_helper=_rc_helper),
    RssListCmd(dao=_dao, rc_helper=_rc_helper),
    RssSubscribeCmd(dao=_dao, rc_helper=_rc_helper, feed_helper=_feed_helper),
)


# glip service
service = GlipService(dao=_dao, rc_helper=_rc_helper, feed_helper=_feed_helper, cmd_services=cmd_services,
                      fetch_period=10)

service.update_feeds_in_background()
