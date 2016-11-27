import logging
from tornado.concurrent import Future

from mongoengine import connect, Document, DynamicDocument
from mongoengine.fields import *

import os

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Connecting to the Database
connect('database', host=os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/'))

class User(Document):
  username = StringField(required=True, unique=True)

class Game(Document):
  game_id = UUIDField(required=True, binary=False)
  players = ListField(ReferenceField(User))
  public = BooleanField(default=True)

class MessageBuffer(object):
  def __init__(self):
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
