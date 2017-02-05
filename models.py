import logging
from tornado.concurrent import Future

from mongoengine import connect
from mongoengine import CASCADE, NULLIFY
from mongoengine import Document, DynamicDocument, EmbeddedDocument
from mongoengine.fields import *

import os

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Connecting to the Database
connect('database', host=os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/'))

# User Model
class User(Document):
  username = StringField(required=True, unique=True)

  def remove_from_games(self):
    for game in Game.objects(players=self):
      game.remove_user(self)

# Game Models
class StockPlayerInfo(EmbeddedDocument):
  stock_id = IntField(required=True)
  player = ReferenceField(User)

class PlayerGameInfo(EmbeddedDocument):
  stocks = ListField(EmbeddedDocumentField(StockPlayerInfo))
  player = ReferenceField(User)

  def __init__(self, user):
    self.player = user
    self.save()

class Stock(EmbeddedDocument):
  name = StringField(required=True)
  prices = ListField(IntField())

class Game(Document):
  game_id = UUIDField(required=True, binary=False)
  players = ListField(ReferenceField(User))
  public = BooleanField(default=True)
  players_info = ListField(EmbeddedDocumentField(PlayerGameInfo))
  stocks = ListField(EmbeddedDocumentField(Stock))

  def add_user(self, user):
    self.players.add(user)
    player_info = PlayerGameInfo(user)
    self.players_info.add(player_info)
    self.save()

  def remove_user(self, user):
    self.players.remove(user)
    self.save()

  def player_count(self):
    return len(self.players)

# Message Models
class Message(Document):
  game_id = ReferenceField(Game, reverse_delete_rule=CASCADE)
  user_id = ReferenceField(User, reverse_delete_rule=NULLIFY)
  content = StringField()

class MessageBuffer(object):
  def __init__(self, game_id):
    self.waiters = set()
    self.cache = []
    self.cache_size = 200

  def wait_for_messages(self, cursor=None):
    # Construct a Future to return to our caller.  This allows
    # wait_for_messages to be yielded from a coroutine even though
    # it is not a coroutine itself.  We will set the result of the
    # Future when results are available.
    result_future = Future()
    if cursor:
      new_count = 0
      for msg in reversed(self.cache):
        if msg["id"] == cursor:
          break
        new_count += 1
      if new_count:
        result_future.set_result(self.cache[-new_count:])
        return result_future
    self.waiters.add(result_future)
    return result_future

  def cancel_wait(self, future):
    self.waiters.remove(future)
    # Set an empty result to unblock any coroutines waiting.
    future.set_result([])

  def new_messages(self, messages):
    logging.info("Sending new message to %r listeners", len(self.waiters))
    for future in self.waiters:
        future.set_result(messages)
    self.waiters = set()
    self.cache.extend(messages)
    if len(self.cache) > self.cache_size:
      self.cache = self.cache[-self.cache_size:]

class GlobalMessageBuffer(object):
  def __init__(self):
    self.messages = {}

  def find(self, game_id):
    if game_id not in self.messages:
      self.messages[game_id] = MessageBuffer()

    return self.messages[game_id]
