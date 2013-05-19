#!/usr/bin/env python
import os
import time

from bottle import route, run, request, post, get, response, delete

import datetime
import json
import redis

SEP = '|'
SYSTEM_NAME = 'wifi'
HOUR_LENGTH = len('2013-05-18T19')
DAY_LENGTH = len('2013-05-18')

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

def get_file_content(filename):
    path = os.path.join(os.path.split(__file__)[0], filename)
    content = file(path).read()
    return content

def unix_to_iso8601(unix):
    if not isinstance(unix, float):
        return None
    if unix == 0.0:
        return None
    return datetime.datetime.fromtimestamp(unix).isoformat()

def hour(unix):
    return unix_to_iso8601(unix)[0:HOUR_LENGTH]

def day(unix):
    return unix_to_iso8601(unix)[0:DAY_LENGTH]

def safe_float(s):
        if s:
            return float(s)
        else:
            return 0.0

class WifiData():
    def __init__(self, client):
        self.r = client
        self.active_mac_set = prefix('active')
        self.mac_to_count_hash = prefix('count')
        self.ping_counter_key = prefix('ping')
        self.last_timestamp_key = prefix('last')

        self.left_mac_by_timestamp_z = prefix('left-by-timestamp')
        self.join_mac_by_timestamp_z = prefix('join-by-timestamp')

        self.excluded_mac_set = prefix('excluded')
        self.hour_set = prefix('hour')
        self.oui_to_manufacturer_hash = 'oui'
        self.started = time.time()

    def agent(self):
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
        return result

    def ping(self):
        m = self.r.pipeline()
        m.set(self.last_timestamp_key, time.time())
        m.incr(self.ping_counter_key)
        return m.execute()

    def join(self, mac, interval=60*60):
        if self.r.sismember(self.active_mac_set, mac):
            return False
        now = time.time()

        m = self.r.pipeline()
        m.sadd(self.active_mac_set, mac)
        m.hincrby(self.mac_to_count_hash, mac, 1)
        # only change join timestamp if the MAC has been away long enough
        if not self._is_recently_active(mac, now, interval):
            m.zadd(self.join_mac_by_timestamp_z, mac, now)
        if not self.r.sismember(self.excluded_mac_set, mac):
            m.hincrby(self.hour_set, hour(now), 1)
        m.execute()

        return True

    def left(self, mac):
        if not self.r.sismember(self.active_mac_set, mac):
            # not joined...
            return False
        m = self.r.pipeline()
        m.srem(self.active_mac_set, mac)
        m.zadd(self.left_mac_by_timestamp_z, mac, time.time())
        m.srem(self.excluded_mac_set, mac)
        m.execute()
        return True

    def purge(self, mac):
        m = self.r.pipeline()
        m.hdel(self.mac_to_count_hash, mac)
        m.srem(self.active_mac_set, mac)
        m.srem(self.excluded_mac_set, mac)
        m.zrem(self.join_mac_by_timestamp_z, mac)
        m.zrem(self.left_mac_by_timestamp_z, mac)
        return m.execute()

    def count(self):
        return len(self._active())

    def macs(self):
        active = self._active()
        macs = self._macs_info(active)
        result = {
            "mac": macs
        }

        return result

    def query(self, start, end):
        results = self.r.zrangebyscore(self.join_mac_by_timestamp_z, start, end)
        macs = self._macs_info(results)
        result = {
            "mac": macs
        }

        return result

    def excluded(self):
        excluded = self._excluded()
        excluded = self._macs_info(excluded)
        result = {
            "mac": excluded
        }

        return result

    def _is_recently_active(self, mac, now, interval):
        last_join = safe_float(self.r.zscore(self.join_mac_by_timestamp_z, mac))
        if (now - last_join) > interval:
            return False
        return True

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
        info['left_iso8601'] = unix_to_iso8601(info['left'])
        info['uptime'] = uptime
        return info

    def _update_fixed(self, mac, uptime, max_uptime=60*60*8):
        if uptime > max_uptime:
            self.r.sadd(self.excluded_mac_set, mac)

    def _fetch_mac(self, mac):
        oui =  mac[0:8]
        m = self.r.pipeline()
        m.zscore(self.join_mac_by_timestamp_z, mac)
        m.hget(self.mac_to_count_hash, mac)
        m.hget(self.oui_to_manufacturer_hash, oui)
        m.zscore(self.left_mac_by_timestamp_z, mac)
        results = m.execute()
        return {
            'joined': float(results[0]),
            'count': int(results[1]),
            'oui': results[2],
            'left': safe_float(results[3])
        }

    def _active(self):
        return self.r.sdiff(self.active_mac_set, self.excluded_mac_set)

    def _excluded(self):
        return self.r.smembers(self.excluded_mac_set)

    def _last(self):
        return safe_float(self.r.get(self.last_timestamp_key))



MAC_REGEXP = '\w{2}:(\w{2}):\w{2}:\w{2}:\w{2}:\w{2}'
MAC_PATH = '<mac:re:%s>' % MAC_REGEXP

@get('/ping')
def ping():
    DATA.ping()

@get('/status.gif')
def status():
    response.headers['Content-Type'] = 'image/gif'

    if DATA.count():
        return OPEN_IMAGE
    else:
        return CLOSE_IMAGE

@get('/agent')
def agent():
    response.headers['Content-Type'] = 'text/json'
    return json.dumps(DATA.agent())

@get('/MAC/%s' % MAC_PATH)
def join(mac):
    DATA.join(mac)

@get('/MAC')
def macs():
    response.headers['Content-Type'] = 'text/json'
    return json.dumps(DATA.macs())

@get('/MAC/count')
def count():
    response.headers['Content-Type'] = 'text/plain'
    return  '%s' % DATA.count()

@get('/MAC/excluded')
def excluded():
    response.headers['Content-Type'] = 'text/json'
    return json.dumps(DATA.excluded())

@delete('/MAC/%s' % MAC_PATH)
def left(mac):
    DATA.left(mac)

@delete('/MAC/purge/%s' % MAC_PATH)
def purge(mac):
    DATA.purge(mac)

@get('/MAC/<start:re:[\.\d]*>/<end:re:[\.\d]*>')
def macs(start, end):
    response.headers['Content-Type'] = 'text/json'
    return json.dumps(DATA.query(start, end))

if __name__ == '__main__':
    global DATA, OPEN_IMAGE, CLOSE_IMAGE
    OPEN_IMAGE = get_file_content('xcj_open_badge.gif')
    CLOSE_IMAGE = get_file_content('xcj_closed_badge.gif')
    DATA = WifiData(client())
    print 'Starting API server'
    run(host='0.0.0.0', reloader=True, port=9000, debug=True)