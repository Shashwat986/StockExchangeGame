import tornado.escape
from tornado import gen
import tornado.web
import uuid

from mongoengine.errors import *
import models

global_message_buffer = models.GlobalMessageBuffer()

class BaseHandler(tornado.web.RequestHandler):
  def get_current_user(self):
    if not self.get_secure_cookie("user"): return None

    username = self.get_secure_cookie("user").decode("utf-8")
    if not username: return None

    try:
      return models.User.objects.get(username=username)
    except DoesNotExist:
      return None

  def set_current_user(self, user):
    self.set_secure_cookie("user", user.username)

  def flash(self, content):
    self.set_secure_cookie("flash", content)

  def render(self, *args, **kwargs):
    kwargs["flash"] = self.get_secure_cookie("flash")
    self.clear_cookie("flash")
    super().render(*args, **kwargs)

class MainHandler(BaseHandler):
  def get(self):
    self.render("index.html")

  def post(self):
    if not self.get_argument('username', None):
      self.flash("Invalid Username")
      self.redirect("/")
      return

    username = self.get_argument('username', None)

    try:
      user = models.User()
      user.username = username
      user.save()
    except NotUniqueError:
      self.flash("This username is already in use")
      self.redirect("/")
      return

    self.set_current_user(user)
    self.flash("Logged In!")
    self.redirect('/')

class LogoutHandler(BaseHandler):
  @tornado.web.authenticated
  def prepare(self):
    self.current_user.remove_from_games()
    self.current_user.delete()
    self.clear_cookie("user")
    self.redirect('/')

class GameHandler(BaseHandler):
  def get(self, g_id = None):
    if not g_id:
      g_id = self.get_query_argument('id', None)

    if g_id and self.current_user:
      self.render("game.html", messages=global_message_buffer.find(g_id).cache)
    else:
      self.redirect("/")

class MessageNewHandler(BaseHandler):
  @tornado.web.authenticated
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

class MessageUpdatesHandler(BaseHandler):
  @tornado.web.authenticated
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
