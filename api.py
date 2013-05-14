#!/usr/bin/env python
import time

from bottle import route, run, request, post, get, response, delete

import redis
import json
import datetime

SEP = '|'
SYSTEM_NAME = 'wifi'

def join_key(*arg):
    return SEP.join(*arg)

def prefix(*arg):
    return join_key([SYSTEM_NAME, SEP.join(list(arg))])

def client(config=None):
    #print dir(redis)
    if config and 'redis' in config:
        redis_config = config['redis']
        print 'Using alternate Redis config %s' % (redis_config)
        return redis.Redis(host=redis_config['host'], port=int(redis_config['port']))
    return redis.Redis()

def unix_to_iso8601(unix):
    return datetime.datetime.fromtimestamp(unix).isoformat()

class WifiData():
    def __init__(self, client):
        self.r = client
        self.active_key = prefix('active')
        self.count_key = prefix('count')
        self.ping_key = prefix('ping')
        self.last_key = prefix('last')
        self.left_key = prefix('left')
        self.join_key = prefix('join')
        self.oui_key = 'oui'
        self.started = time.time()

    def ping(self):
        m = self.r.pipeline()
        m.set(self.last_key, time.time())
        m.incr(self.ping_key)
        return m.execute()

    def join(self, mac):
        if self.r.sismember(self.active_key, mac):
            # already seen
            return 0
        m = self.r.pipeline()
        m.sadd(self.active_key, mac)
        m.hset(self.join_key, mac, time.time())
        m.incr(self.count_key)
        return m.execute()

    def left(self, mac):
        if not self.r.sismember(self.active_key, mac):
            # not joined...
            return 0
        m = self.r.pipeline()
        m.srem(self.active_key, mac)
        m.hset(self.left_key, mac, time.time())
        return m.execute()

    def count(self):
        response.headers['Content-Type'] = 'text/plain'
        return '%s' % self.r.scard(self.active_key)

    def list(self):
        response.headers['Content-Type'] = 'text/json'
        macs = {}
        last = self.r.get(self.last_key)
        if last:
            last = float(last)
        else:
            last = 0
        agent = {
            'last': last,
            'last_iso8601': unix_to_iso8601(last),
            'delta': time.time() - last,
            'total': self.r.hlen(self.count_key),
            'ping': self.r.get(self.ping_key),
            'started': self.started,
            'started_iso8601': unix_to_iso8601(self.started)
        }
        for mac in self.r.smembers(self.active_key):
            joined = float(self.r.hget(self.join_key, mac))
            oui =  mac[0:8]
            macs[mac] = {
                'oui': self.r.hget(self.oui_key, oui),
                'joined': joined,
                'joined_iso8601': unix_to_iso8601(joined),
                'uptime': int(time.time() - joined),
                'count': self.r.hget(self.count_key, mac)
            }
        result = {
            "agent": agent,
            "mac": macs
        }
        return json.dumps(result)


@get('/ping')
def ping():
    DATA.ping()

@get('/MAC/<mac>')
def join(mac):
    DATA.join(mac)

@get('/MAC')
def list_macs():
    return DATA.list()

@get('/MAC/count')
def count():
    return DATA.count()

@delete('/MAC/<mac>')
def left(mac):
    DATA.left(mac)

if __name__ == '__main__':
    global DATA
    DATA = WifiData(client())

    run(host='0.0.0.0', port=9000, debug=True)