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

  def game_config(self, g_id = None):
    if not g_id:
      g_id = self.get_argument('id', None)

    if g_id:
      try:
        self.game = models.Game.objects.get(id=g_id)
      except (DoesNotExist, ValidationError):
        self.set_status(400, "Invalid Game ID")
        self.write("")
        self.finish()
    else:
      self.game = None

class MainHandler(BaseHandler):
  def get(self):
    self.render("index.html", **{
      'games': models.Game.objects(public=True)
    })

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
  @tornado.web.authenticated
  def get(self, g_id = None):
    self.game_config(g_id)
    if self.game:
      if self.get_current_user() in self.game.players:
        self.render("game.html", **{
          "messages": global_message_buffer.find(self.game).all_messages(),
          "game": self.game
        })
        self.finish()

    self.redirect("/")

  @tornado.web.authenticated
  def post(self, g_id = None):
    self.game_config(g_id)
    if not self.game:
      self.game = models.Game()
      self.game.save()

    user = self.get_current_user()
    self.game.add_user(user)

    self.redirect("/game/" + str(self.game.id))

class MessageHandler(BaseHandler):
  @tornado.web.authenticated
  def post(self):
    # Create a new message
    self.game_config()

    if self.game:
      message = models.Message(**{
        'body': self.get_argument("body"),
        'user_id': self.get_current_user(),
        'game_id': self.game
      })
      message.save_()

      self.write(message.get_hash())
      global_message_buffer.find(self.game).new_messages([message])
    else:
      self.set_status(400, "Invalid Game ID")
      self.write("")

  @tornado.web.authenticated
  @gen.coroutine
  def put(self):
    # Send updates to all waiters
    self.game_config()

    cursor = self.get_argument("cursor", None)

    if self.game:
      # Save the future returned by wait_for_messages so we can cancel
      # it in wait_for_messages
      self.future = global_message_buffer.find(self.game).wait_for_messages(cursor=cursor)

      messages = yield self.future
      if self.request.connection.stream.closed():
        return

      self.write(dict(messages=list(map(lambda x: x.get_hash(), messages))))
    else:
      self.set_status(400, "Invalid Game ID")
      self.write("")

  def on_connection_close(self):
    global_message_buffer.find(self.game).cancel_wait(self.future)
