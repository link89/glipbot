import abc
import os
import re
import time
import pickle
import asyncio
from boltons.strutils import html2text

from tornado.platform.asyncio import convert_yielded

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
    patterns = None

    def parse(self, post) -> Optional[tuple]:
        if self.pattern is None:
            patterns = self.patterns
        else:
            patterns = (self.pattern,)
        text = self.get_text(post).strip()
        for pattern in patterns:
            match = pattern.match(text)
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


class RssHelpCmd(BaseCmd):
    """
    this command is for debug
    """
    pattern = re.compile(r"^rss\s+help$")

    def __init__(self, rc_helper: RcPlatformHelper):
        self.rc_helper = rc_helper

    async def run(self, post, *args):
        group_id = self.get_group_id(post)
        msg = '\n'.join((
            "[code]Welcome to use Glip RSS Bot! (Powered by Python 3.6, Tornado and feedparser!)",
            "",
            "rss help",
            "  Print this usage",
            "",
            "rss list",
            "  List all feeds",
            "",
            "rss subscribe FEED_URI",
            "  Subscribe feed",
            "",
            "rss feed FEED_ID unsubscribe",
            "  Unsubscribe feed",
            "",
            "rss search REGEX",
            "rss feed FEED_ID search REGEX",
            "  Search feed",
        ))
        self.rc_helper.post_to_group(group_id, msg)


class RssSubscribeCmd(BaseCmd):
    """
    subscribe to rss feed
    """
    pattern = re.compile(r"^rss\s+subscribe\s+([^\s]+)$")

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
            # here we set last_updated to one day before now for new subscription
            # so that the subscriber will receive the update within one day
            last_updated = int(time.time()) - 3600 * 24
            self.dao.update_or_create_subscription(group_id, feed.id, last_updated=last_updated)
            msg = "Successfully subscribe feed {} !".format(uri)
            self.rc_helper.post_to_group(group_id, msg)


class RssUnsubscribeCmd(BaseCmd):
    pattern = re.compile(r"^rss\s+feed\s+(\d+)\s+unsubscribe$")

    def __init__(self, dao: Dao, rc_helper: RcPlatformHelper):
        self.dao = dao
        self.rc_helper = rc_helper

    async def run(self, post, feed_id: str, *args):
        feed_id = int(feed_id)
        group_id = self.get_group_id(post)
        if self.dao.delete_subscriptions(group_id=group_id, feed_id=feed_id):
            msg = "Successfully unsubscribe feed {} !".format(feed_id)
        else:
            msg = "Fail to unsubscribe feed {}! " \
                  "Please run following command to check your feed id!" \
                  "[code] rss list".format(feed_id)
        self.rc_helper.post_to_group(group_id, msg)


class RssListCmd(BaseCmd):
    pattern = re.compile(r"^rss\s+list$")

    def __init__(self, dao: Dao, rc_helper: RcPlatformHelper):
        self.dao = dao
        self.rc_helper = rc_helper

    async def run(self, post, *args):
        group_id = self.get_group_id(post)
        subscriptions = self.dao.get_subscriptions(group_id=group_id, lazy=False)
        cards = []
        for subscription in subscriptions:
            title = "{} {}".format(str(subscription.feed_id).ljust(5), subscription.feed.title)
            card = self.rc_helper.new_simple_card(
                title=self.rc_helper.new_link(title, subscription.feed.uri),
            )
            cards.append(card)
        if cards:
            text = "You have subscribed {} feeds!".format(len(cards))
            data = self.rc_helper.new_simple_cards(text=text, cards=cards)
        else:
            text = "You don't yet subscribe any feeds! Subscribe your first feed by following command: " \
                   "[code] rss subscribe FEED_URI"
            data = self.rc_helper.new_simple_cards(text=text)
        self.rc_helper.post_to_group(group_id, data)


class RssSearchCmd(BaseCmd):
    patterns = (
        re.compile(r"^rss\s+feed\s+(\d+)\s+search\s+(.*)"),
        re.compile(r"^rss\s+search\s+(.*)"),
    )

    def __init__(self, dao: Dao, rc_helper: RcPlatformHelper):
        self.dao = dao
        self.rc_helper = rc_helper

    async def run(self, post, *args):
        group_id = self.get_group_id(post)
        if len(args) == 2:
            feed_id, keywords = args
            feed_id = int(feed_id)
        else:
            feed_id = None
            keywords: str = args[0]
        pattern = re.compile(keywords, flags=re.IGNORECASE)
        subscriptions = self.dao.get_subscriptions(group_id=group_id, feed_id=feed_id)
        feed_ids = [sub.feed_id for sub in subscriptions]
        entries = []
        for feed_id in feed_ids:
            for entry in self.dao.get_entries(feed_id=feed_id):
                if pattern.search(entry.title) or pattern.search(entry.summary):
                    entries.append(entry)

        cards = []
        for entry in entries:
            card = self.rc_helper.new_simple_card(
                title=self.rc_helper.new_link(entry.title, entry.link),
                text=html2text(entry.summary),
                thumbnail_uri=entry.thumbnail,
            )
            cards.append(card)
        if cards:
            text = "{} entries match {} !".format(len(cards), keywords)
            logger.info(text)
            data = self.rc_helper.new_simple_cards(text=text, cards=cards)
        else:
            data = text = "No entry match {} !".format(keywords)
        logger.info(text)
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

    async def update_subscription(self, subscription: Subscription):
        logger.info("update subscription: start to update %s for %s", subscription.feed.title, subscription.group_id)
        entries = self.dao.get_entries(subscription.feed_id, last_updated=subscription.last_updated)
        cards = []
        for entry in entries:
            card = self.rc_helper.new_simple_card(
                title=self.rc_helper.new_link(entry.title, entry.link),
                text=html2text(entry.summary),
                thumbnail_uri=entry.thumbnail,
            )
            cards.append(card)
        if cards:
            text = "You have {} new entries from {}!".format(len(cards), subscription.feed.title)
            logger.info(text)
            data = self.rc_helper.new_simple_cards(text=text, cards=cards)
            self.rc_helper.post_to_group(subscription.group_id, data)
            self.dao.update_or_create_subscription(
                group_id=subscription.group_id, feed_id=subscription.feed_id,
                last_updated=max(e.last_updated for e in entries),
            )
            logger.info("update subscription: success to update %s for %s", subscription.feed.title, subscription.group_id)

    async def update_subscriptions(self):
        while True:
            logger.info("update subscriptions: start")
            futures = list(self.update_subscription(sub) for sub in self.dao.get_subscriptions(lazy=False))
            futures.append(asyncio.sleep(self.push_period))
            done, pending = await asyncio.wait(futures, timeout=self.fetch_period, return_when=asyncio.ALL_COMPLETED)
            for future in pending:
                future.cancel()
            logger.info("update subscriptions: done")

    def update_feeds_in_background(self):
        convert_yielded(self.update_feeds())

    def update_subscriptions_in_background(self):
        convert_yielded(self.update_subscriptions())


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
    RssHelpCmd(rc_helper=_rc_helper),
    RssListCmd(dao=_dao, rc_helper=_rc_helper),
    RssSubscribeCmd(dao=_dao, rc_helper=_rc_helper, feed_helper=_feed_helper),
    RssUnsubscribeCmd(dao=_dao, rc_helper=_rc_helper),
    RssSearchCmd(dao=_dao, rc_helper=_rc_helper),
)


# glip service
service = GlipService(dao=_dao, rc_helper=_rc_helper, feed_helper=_feed_helper, cmd_services=cmd_services,
                      fetch_period=10, push_period=10)

service.update_feeds_in_background()
service.update_subscriptions_in_background()
