from boltons.cacheutils import cachedproperty
import feedparser

from ringcentral.platform.platform import Platform
from tornado.httpclient import AsyncHTTPClient


class RcPlatformHelper(object):
    def __init__(self, platform: Platform):
        self.platform = platform

    @cachedproperty
    def me(self):
        res = self.platform.get('/glip/persons/~')
        return res.json_dict()

    def create_or_get_private_group(self, person_id):
        members = [str(person_id), self.me['id']]
        data = {
            'members': members,
            'type': 'PrivateChat'
        }
        res = self.platform.post('/glip/groups', body=data)
        return res.json_dict()

    def post_to_group(self, group_id, data):
        if isinstance(data, str):
            data = {'text': data}
        res = self.platform.post('/glip/groups/{}/posts'.format(group_id), body=data)
        return res.json_dict()

    def post_to_person(self, person_id, data):
        group = self.create_or_get_private_group(person_id)
        return self.post_to_group(group['id'], data)

    def subscribe_webhook(self, address, event_filters=None, expires_in=500000000):
        if event_filters is None:
            event_filters = [
                "/restapi/v1.0/glip/posts",
                "/restapi/v1.0/glip/groups",
            ]
        data = {
            "eventFilters": event_filters,
            "deliveryMode": {
                "transportType": "WebHook",
                "address": address,
            },
            "expiresIn": expires_in,
        }

        res = self.platform.post('/subscription', body=data)
        return res.json_dict()


class FeedHelper(object):
    def __init__(self, http=None):
        self._http: AsyncHTTPClient = AsyncHTTPClient() if http is None else http

    async def get_feed(self, url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.116 Safari/537.36'
        }
        res = await self._http.fetch(url, headers=headers)
        return res

    @staticmethod
    def parse(data):
        feed = feedparser.parse(data)
        if feed.bozo != 0:
            raise RuntimeError("error occur during parsing rss feed: {}".format(data))
        return feed

    @staticmethod
    def get_feed_href(feed, default=None):
        return feed.get("href", default)

    @staticmethod
    def get_feed_title(feed):
        return feed.feed.title

    @staticmethod
    def get_entries(feed):
        return feed.entries
