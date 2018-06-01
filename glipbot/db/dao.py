from typing import Optional, Sequence
from sqlalchemy.orm import joinedload
from .schemas import Session
from .schemas import (
    Feed,
    Subscription,
    Entry,
)


class Dao(object):
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or Session

    def get_feed(self, href):
        session = self.session_factory()
        try:
            feed = session.query(Feed).filter_by(href=href).first()
        finally:
            session.close()
        return feed

    def get_or_create_feed(self, href, title):
        session = self.session_factory()
        try:
            feed = session.query(Feed).filter_by(href=href).first()
            if feed is None:
                feed = Feed(href=href)
                session.add(feed)
            feed.title = title
        except Exception as e:
            session.rollback()
            raise e
        else:
            session.commit()
        finally:
            session.close()
        return feed

    def get_subscription(self, group_id, feed_id) -> Optional[Subscription]:
        subscriptions = self.get_subscriptions(group_id, feed_id)
        if len(subscriptions) > 0:
            return subscriptions[0]
        return None

    def get_subscriptions(self, group_id=None, feed_id=None, lazy=True) -> Sequence[Subscription]:
        session = self.session_factory()
        try:
            query = session.query(Subscription)
            if not lazy:
                query = query.options(joinedload(Subscription.feed))
            if group_id is not None:
                query = query.filter_by(group_id=group_id)
            if feed_id is not None:
                query = query.filter_by(feed_id=feed_id)
            subscriptions = query.all()
        finally:
            session.close()
        return subscriptions

    def get_or_create_subscription(self, group_id, feed_id):
        session = self.session_factory()
        try:
            subscription = session.query(Subscription) \
                .filter_by(group_id=group_id) \
                .filter_by(feed_id=feed_id) \
                .first()
            if subscription is None:
                subscription = Subscription(group_id=group_id, feed_id=feed_id)
                session.add(subscription)
        except Exception as e:
            session.rollback()
            raise e
        else:
            session.commit()
        finally:
            session.close()
        return subscription
