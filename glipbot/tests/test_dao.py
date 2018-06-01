import unittest
from ..db.schemas import Session
from ..db.dao import Dao


class TestDao(unittest.TestCase):

    def setUp(self):
        self.dao = Dao(session_factory=Session)

    def test_feed(self):
        href = "http://www.solidot.org/index.rss"
        feed = self.dao.get_or_create_feed(href)
        print(feed)
        subscription = self.dao.get_or_create_subscription("123", feed.id)
        print(subscription)

