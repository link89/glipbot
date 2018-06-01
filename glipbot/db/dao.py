import time
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

    def get_feeds(self,) -> Sequence[Feed]:
        session = self.session_factory()
        try:
            feeds = session.query(Feed).all()
        finally:
            session.close()
        return feeds

    def update_or_create_feed(self, uri, title, last_updated=None):
        if last_updated is None:
            last_updated = int(time.time())
        session = self.session_factory()
        try:
            feed = session.query(Feed).filter_by(uri=uri).first()
            if feed is None:
                feed = Feed(uri=uri)
                session.add(feed)
            feed.title = title
            feed.last_updated = last_updated
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

    def update_or_create_subscription(self, group_id, feed_id, last_updated=None):
        session = self.session_factory()
        try:
            subscription = session.query(Subscription) \
                .filter_by(group_id=group_id) \
                .filter_by(feed_id=feed_id) \
                .first()
            if subscription is None:
                subscription = Subscription(group_id=group_id, feed_id=feed_id)
                session.add(subscription)
            if last_updated is not None:
                subscription.last_updated = last_updated
        except Exception as e:
            session.rollback()
            raise e
        else:
            session.commit()
        finally:
            session.close()
        return subscription

    def update_or_create_entry(self, feed_id, key, title, link, summary, thumbnail, last_updated):
        session = self.session_factory()
        try:
            entry = session.query(Entry) \
                .filter_by(feed_id=feed_id) \
                .filter_by(key=key) \
                .first()
            if entry is None:
                entry = Entry(feed_id=feed_id, key=key)
                session.add(entry)
            entry.title = title
            entry.link = link
            entry.summary = summary
            entry.thumbnail = thumbnail
            entry.last_updated = last_updated
        except Exception as e:
            session.rollback()
            raise e
        else:
            session.commit()
        finally:
            session.close()

    def get_entries(self, feed_id=None, last_updated=None):
        session = self.session_factory()
        try:
            query = session.query(Entry)
            if feed_id is not None:
                query = query.filter_by(feed_id=feed_id)
            if last_updated is not None:
                query = query.filter(Entry.last_updated > last_updated)
            entries = query.all()
        finally:
            session.close()
        return entries


