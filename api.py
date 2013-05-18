#!/usr/bin/env python
import time

from bottle import route, run, request, post, get, response, delete

import redis
import json
import datetime

SEP = '|'
SYSTEM_NAME = 'wifi'

def join_args(*arg):
    return SEP.join(*arg)

def prefix(*arg):
    return join_args([SYSTEM_NAME, SEP.join(list(arg))])

def client(config=None):
    #print dir(redis)
    if config and 'redis' in config:
        redis_config = config['redis']
        print 'Using alternate Redis config %s' % (redis_config)
        return redis.Redis(host=redis_config['host'], port=int(redis_config['port']))
    return redis.Redis()

def unix_to_iso8601(unix):
    return datetime.datetime.fromtimestamp(unix).isoformat()

HOUR_LENGTH = len('2013-05-18T19')

def hour(unix):
    return unix_to_iso8601(unix)[0:HOUR_LENGTH]

class WifiData():
    def __init__(self, client):
        self.r = client
        self.active_mac_set = prefix('active')
        self.mac_to_count_hash = prefix('count')
        self.ping_counter_key = prefix('ping')
        self.last_timestamp_key = prefix('last')
        self.left_mac_to_timestamp_hash = prefix('left')
        self.join_mac_to_timestamp_hash = prefix('join')
        self.excluded_mac_set = prefix('excluded')
        self.hour_set = prefix('hour')
        self.oui_to_manufacturer_hash = 'oui'
        self.started = time.time()

    def ping(self):
        m = self.r.pipeline()
        m.set(self.last_timestamp_key, time.time())
        m.incr(self.ping_counter_key)
        return m.execute()

    def join(self, mac):
        if self.r.sismember(self.active_mac_set, mac):
            # already seen
            return 0

        now = time.time()

        m = self.r.pipeline()
        m.sadd(self.active_mac_set, mac)
        m.hset(self.join_mac_to_timestamp_hash, mac, now)
        m.hincrby(self.mac_to_count_hash, mac, 1)
        if not self.r.sismember(self.excluded_mac_set, mac):
            m.hincrby(self.hour_set, hour(now), 1)
        results = m.execute()

    def left(self, mac):
        if not self.r.sismember(self.active_mac_set, mac):
            # not joined...
            return 0
        m = self.r.pipeline()
        m.srem(self.active_mac_set, mac)
        m.hset(self.left_mac_to_timestamp_hash, mac, time.time())
        m.srem(self.excluded_mac_set, mac)
        return m.execute()

    def count(self):
        response.headers['Content-Type'] = 'text/plain'
        return '%s' % len(self._active())

    def agent(self):
        response.headers['Content-Type'] = 'text/json'
        last = self._last()
        agent = {
            'last': last,
            'last_iso8601': unix_to_iso8601(last),
            'delta': time.time() - last,
            'total': self.r.hlen(self.mac_to_count_hash),
            'ping': self.r.get(self.ping_counter_key),
            'started': self.started,
            'started_iso8601': unix_to_iso8601(self.started),
            'active': self.r.scard(self.active_mac_set)
        }
        result = {
            "agent": agent
        }
        return json.dumps(result)

    def macs(self):
        response.headers['Content-Type'] = 'text/json'

        active = self._active()
        macs = self._macs_info(active)
        result = {
            "mac": macs
        }

        return json.dumps(result)

    def excluded(self):
        response.headers['Content-Type'] = 'text/json'

        excluded = self._excluded()
        excluded = self._macs_info(excluded)
        result = {
            "mac": excluded
        }

        return json.dumps(result)

    def _macs_info(self, macs_list):
        macs = {}

        for mac in macs_list:
            macs[mac] = self._mac_info(mac)

        return macs

    def _mac_info(self, mac):
        info = self._fetch_mac(mac)
        uptime = int(time.time() - info['joined'])
        self._update_fixed(mac, uptime)
        info['joined_iso8601'] = unix_to_iso8601(info['joined'])
        info['uptime'] = uptime
        return info

    def _update_fixed(self, mac, uptime, max_uptime=60*60*8):
        if uptime > max_uptime:
            self.r.sadd(self.excluded_mac_set, mac)

    def _fetch_mac(self, mac):
        oui =  mac[0:8]
        m = self.r.pipeline()
        m.hget(self.join_mac_to_timestamp_hash, mac)
        m.hget(self.mac_to_count_hash, mac)
        m.hget(self.oui_to_manufacturer_hash, oui)
        results = m.execute()
        return {
            'joined': float(results[0]),
            'count': int(results[1]),
            'oui': results[2]
        }

    def _active(self):
        return self.r.sdiff(self.active_mac_set, self.excluded_mac_set)

    def _excluded(self):
        return self.r.smembers(self.excluded_mac_set)

    def _last(self):
        last = self.r.get(self.last_timestamp_key)
        if last:
            return float(last)
        else:
            return 0

@get('/ping')
def ping():
    DATA.ping()

@get('/agent')
def agent():
    return DATA.agent()

@get('/MAC/<mac>')
def join(mac):
    DATA.join(mac)

@get('/MAC')
def macs():
    return DATA.macs()

@get('/MAC/count')
def count():
    return DATA.count()

@get('/MAC/excluded')
def excluded():
    return DATA.excluded()

@delete('/MAC/<mac>')
def left(mac):
    DATA.left(mac)

if __name__ == '__main__':
    global DATA
    DATA = WifiData(client())
    print 'Starting API server'
    run(host='0.0.0.0', reloader=True, port=9000, debug=True)