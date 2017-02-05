from controllers import *

routes = [
  (r"/", MainHandler),
  (r"/logout", LogoutHandler),
  (r"/game", GameHandler),
  (r"/game/(.*)", GameHandler),
  (r"/a/message/new", MessageHandler),
  (r"/a/message/updates", MessageHandler),
]
