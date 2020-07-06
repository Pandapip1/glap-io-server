import random
import traceback
from threading import Thread

import mysql.connector
import tornado.httpserver
import tornado.websocket
import tornado.web
import tornado.ioloop
import tornado.gen
import asyncio


# from profanity_check import predict as is_profane

def is_profane(word):
    return [False]


import gamedaemon
import os
import time

prefixes = {}
users = {}
isconnected = {}
session2id = {}
canupdatewld = {}
websockets = []


OFFLINE = False

def choosenm(websocket, message):
  asyncio.set_event_loop(asyncio.new_event_loop())
  print(message[1] + " tried to connect.")
  nt = False
  save = "[0,[null,null,null,null]]"
  if not OFFLINE:
      db = mysql.connector.connect(
          host=os.getenv("DB_HOST"),
          user=os.getenv("DB_USER"),
          passwd=os.getenv("DB_PASS"),
          database=os.getenv("DB_DB")
      )
      cursor = db.cursor()
      cursor.execute("SELECT UID, savednames FROM users")
      for savednames in cursor.fetchall():
          if savednames[0] == message[2]:
              continue
          savednames = savednames[1].split(",")
          if message[1] in savednames:
              nt = True
      fetchone = ""
      if message[2] != "none":
          cursor.execute("SELECT saves FROM users WHERE UID='" + message[2] + "'")
          fetchone = cursor.fetchone()[0]
      save = fetchone if fetchone != "" else "[0,[null,null,null,null]]"
      db.disconnect()
  if message[1] in users.values() or nt:
      websocket.write_message(u"nametaken")
  elif is_profane([message[1]])[0]:
      websocket.write_message(u"profanename")
  elif gamedaemon.adduser(message[1], save,
                          "0" if message[2] == "null" else str(getprefixint(message[2]))):
      sessid = -1
      while sessid == -1 or str(sessid) in users.keys():
          sessid = int(random.random() * 1000000)
      users[str(sessid)] = message[1]
      session2id[sessid] = None if message[2] == "null" else message[2]
      websocket.write_message(u"setsessid " + str(sessid))
  else:
      websocket.write_message(u"setnmerror")

def setsessid(websocket, message):
  asyncio.set_event_loop(asyncio.new_event_loop())
  websocket.sessid = message[1]
  websocket.user = users[websocket.sessid]
  websocket.write_message("sessidset")
  websockets.append(websocket)

def save(uid):
  asyncio.set_event_loop(asyncio.new_event_loop())
  db = mysql.connector.connect(
      host=os.getenv("DB_HOST"),
      user=os.getenv("DB_USER"),
      passwd=os.getenv("DB_PASS"),
      database=os.getenv("DB_DB")
  )
  cursor = db.cursor()
  cursor.execute(
      "UPDATE users SET saves = \"" + gamedaemon.getshipstring(users[uid]) + "\" WHERE uid = \"" +
      session2id[int(uid)] + "\"")
  db.commit()
  db.disconnect()

def sendworlds():
  asyncio.set_event_loop(asyncio.new_event_loop())
  while True:
    for websocket in websockets:
      websocket.write_message(u"w " + gamedaemon.get_world_2(websocket.user))
    time.sleep(.05)

def getroles(uid):
    asyncio.set_event_loop(asyncio.new_event_loop())
    if OFFLINE:
        return [False for i in range(4)]
    db = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        passwd=os.getenv("DB_PASS"),
        database=os.getenv("DB_DB")
    )
    cursor = db.cursor()
    cursor.execute("SELECT roles FROM users WHERE uid='" + str(uid) + "'")
    roles = '{:>08d}'.format(int(bin(cursor.fetchone()[0])[2:]))[::-1]
    db.disconnect()
    return [roles[i] == "1" for i in range(4)]


def getprefixint(uid):
    roles = getroles(uid)
    if roles[0]:
        return 2
    if roles[1]:
        return 3
    if roles[2]:
        return 4
    return 1


def uptick():
    if OFFLINE: return
    num = 0
    while True:
        try:
            db = mysql.connector.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                passwd=os.getenv("DB_PASS"),
                database=os.getenv("DB_DB")
            )
            cursor = db.cursor()
            for i in session2id.values():
                if i is None:
                    continue
                cursor.execute("UPDATE users SET xp = xp+1 WHERE UID = '" + i + "'")
                if num % 10 == 0:
                    cursor.execute("UPDATE users SET coins = coins+1 WHERE UID = '" + i + "'")
                cursor.execute("SELECT ref FROM users WHERE UID = '" + i + "'")
                try:
                    ref = cursor.fetchone()[0]
                    if num % 100 == 0:
                        cursor.execute("UPDATE users SET coins = coins+1 WHERE UID = '" + ref + "'")
                        cursor.execute("UPDATE users SET creditsduetoref = creditsduetoref+1 WHERE UID = '" + ref + "'")
                    if num % 10 == 0:
                        cursor.execute("UPDATE users SET xp = xp+1 WHERE UID = '" + ref + "'")
                        cursor.execute("UPDATE users SET xpduetoref = xpduetoref+1 WHERE UID = '" + ref + "'")
                except Exception:
                    ...
            db.commit()
            db.disconnect()
            num += 1
            time.sleep(3)
        except Exception:
            ...


class GameDaemonWebSocket(tornado.websocket.WebSocketHandler):
    def open(self):
        print("WebSocket opened")
        self.set_nodelay(True)

    async def on_message(self, message):
        try:
            message = message.split(" ")
            if message[0] == "setsessid":
                Thread(target=setsessid, args=(self, message)).start()
            if message[0] == "trigger":
                Thread(target=gamedaemon.trigger, args=(self.user, int(message[1]), int(message[2]) != 0)).start()
            if message[0] == "mup":
              Thread(target=gamedaemon.mouse, args=(self.user, False, False, 0, 0)).start()
            if message[0] == "mdown":
              Thread(target=gamedaemon.mouse, args=(self.user, False, True, 0, 0)).start()
            if message[0] == "mmove":
              Thread(target=gamedaemon.mouse, args=(self.user, True, False, float(message[1]), float(message[2]))).start()
            if message[0] == "save" and not OFFLINE:
                if session2id[int(message[1])] is not None:
                    Thread(target=save, args=(message[1],)).start()
            if message[0] == "choosenm":
                print("choosenm recieved")
                Thread(target=choosenm, args=(self, message)).start()
        except Exception as e:
            traceback.print_exc()
            self.write_message(u"error")
            gamedaemon.removeuser(message[1])

    def on_close(self):
        if hasattr(self, "sessid"):
          gamedaemon.removeuser(users[self.sessid])
          del isconnected[self.sessid]
          del users[self.sessid]
          del session2id[self.sessid]
          del prefixes[self.sessid]
          websockets.remove(websocket)
        print("WebSocket closed")

    def check_origin(self, origin):
        return True

    def get_compression_options(self):
        return {'compression_level': 8, 'mem_level': 8}


application = tornado.web.Application([
    (r'/', GameDaemonWebSocket),
])

if __name__ == "__main__":
    gamedaemon.trigger_start()
    Thread(target=uptick, daemon=True).start()
    Thread(target=sendworlds, daemon=True).start()
    http_server = tornado.httpserver.HTTPServer(application, max_body_size=10000000)
    http_server.listen(os.getenv("PORT", 6155))
    tornado.ioloop.IOLoop.instance().start()
