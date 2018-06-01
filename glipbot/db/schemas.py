from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.orm.session import sessionmaker

from ..import config

Base = declarative_base()


class Feed(Base):
    __tablename__ = 'feed'
    id = Column(Integer, primary_key=True)
    href = Column(String(250))
    title = Column(String(250))
    subscriptions = relationship('Subscription', back_populates="feed")
    entries = relationship('Entry', back_populates="feed")


class Subscription(Base):
    __tablename__ = 'subscription'
    id = Column(Integer, primary_key=True)
    group_id = Column(String(32))

    feed_id = Column(Integer, ForeignKey(Feed.id))
    feed = relationship(Feed, back_populates="subscriptions")


class Entry(Base):
    __tablename__ = 'entry'
    id = Column(Integer, primary_key=True)
    title = Column(String(250))
    link = Column(String(250))
    data = Column(Text())

    feed_id = Column(Integer, ForeignKey(Feed.id))
    feed = relationship(Feed, back_populates="entries")


if config.MODE == "DEBUG":
    url = config.DEBUG_DB_URL
else:
    url = config.DB_URL

engine = create_engine(url)

Session = sessionmaker(expire_on_commit=False)
Session.configure(bind=engine)


def create_tables():
    Base.metadata.create_all(engine)


if __name__ == '__main__':
    create_tables()
