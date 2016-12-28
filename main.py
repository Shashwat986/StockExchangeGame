#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import tornado.ioloop
import tornado.web
import os

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from tornado.options import define, options, parse_command_line

define("port", default=os.environ.get("PORT", 8888), help="run on the given port", type=int)
define("debug", default=False, help="run in debug mode")

from controllers import *

def main():
  parse_command_line()
  print("Debug Mode: ", options.debug)
  print("Port: ", options.port)
  app = tornado.web.Application(
    [
      (r"/", MainHandler),
      (r"/logout", LogoutHandler),
      (r"/game", GameHandler),
      (r"/game/(.*)", GameHandler),
      (r"/a/message/new", MessageNewHandler),
      (r"/a/message/updates", MessageUpdatesHandler),
    ],
    cookie_secret=os.environ.get("SECRET_KEY"),
    template_path=os.path.join(os.path.dirname(__file__), "templates"),
    static_path=os.path.join(os.path.dirname(__file__), "static"),
    xsrf_cookies=True,
    debug=options.debug,
  )
  app.listen(options.port)
  tornado.ioloop.IOLoop.current().start()

if __name__ == "__main__":
  main()
