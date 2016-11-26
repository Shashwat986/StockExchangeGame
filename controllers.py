import tornado.escape
from tornado import gen
import tornado.web
import uuid

from models import global_message_buffer

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")

class GameHandler(tornado.web.RequestHandler):
    def get(self):
        g_id = self.get_query_argument('id', None)
        if g_id:
          self.render("game.html", messages=global_message_buffer.find(g_id).cache)
        else:
          self.redirect("/")

class MessageNewHandler(tornado.web.RequestHandler):
    def post(self):
        message = {
            "id": str(uuid.uuid4()),
            "body": self.get_argument("body"),
        }

        g_id = self.get_argument('game_id', None)
        if g_id:
          # to_basestring is necessary for Python 3's json encoder,
          # which doesn't accept byte strings.
          message["html"] = tornado.escape.to_basestring(
              self.render_string("sidebar/message.html", message=message))

          self.write(message)
          global_message_buffer.find(g_id).new_messages([message])
        else:
          self.set_status(400, "Invalid Game ID")
          self.write("")

class MessageUpdatesHandler(tornado.web.RequestHandler):
    @gen.coroutine
    def post(self):
        cursor = self.get_argument("cursor", None)

        g_id = self.get_argument('game_id', None)
        if g_id:
          # Save the future returned by wait_for_messages so we can cancel
          # it in wait_for_messages
          self.future = global_message_buffer.find(g_id).wait_for_messages(cursor=cursor)
          self.game_id = g_id

          messages = yield self.future
          if self.request.connection.stream.closed():
              return
          self.write(dict(messages=messages))
        else:
          self.set_status(400, "Invalid Game ID")
          self.write("")

    def on_connection_close(self):
        global_message_buffer.find(self.game_id).cancel_wait(self.future)
