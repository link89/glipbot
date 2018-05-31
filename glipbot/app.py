import asyncio

from tornado.platform.asyncio import AsyncIOMainLoop
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.auth
import tornado.gen
import tornado.concurrent
import tornado.web


from config import PORT, TORNADO_SETTINGS


class HealthHandler(tornado.web.RequestHandler):
    async def get(self):
        self.finish('glip bot is running!')


def main():
    AsyncIOMainLoop().install()
    # NOTE: path here should end with /?$ for compatibility
    # NOTE: use named group so that apispec could generate proper path pattern
    endpoints = [
        (r"^/health/?$", HealthHandler),
    ]
    application = tornado.web.Application(endpoints, **TORNADO_SETTINGS)
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(PORT)
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
