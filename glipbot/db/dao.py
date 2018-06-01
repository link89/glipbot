from sqlalchemy.orm import raiseload
from .schemas import (
    Feed,
    Subscription,
    Entry,
)


class Dao(object):
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def get_or_create_feed(self, href):
        session = self.session_factory()
        try:
            feed = session.query(Feed).filter_by(href=href).first()
            if feed is None:
                feed = Feed(href=href)
                session.add(feed)
        except Exception as e:
            session.rollback()
            raise e
        else:
            session.commit()
        finally:
            session.close()
        return feed

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
