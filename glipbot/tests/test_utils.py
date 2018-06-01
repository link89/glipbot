import tornado.testing

from ..utils.clients import FeedHelper


class TestSeleniumGridClient(tornado.testing.AsyncTestCase):
    @tornado.testing.gen_test
    async def test_get_devices(self):
        helper = FeedHelper()
        res = await helper.get_feed("http://www.solidot.org/index.rss")
        feed = helper.parse(res.body)
        print(feed)
