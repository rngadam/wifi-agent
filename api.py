#!/usr/bin/env python
from apscheduler.scheduler import Scheduler
from bottle import route, run, request, post, get, response, delete

import argparse
import datetime
import json
import logging
import os
import re
import redis
import time

SUBDIR = 'logs'


def getLogger(filename):
    name = os.path.basename(filename).split('.')[0]
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    subdir = os.path.join(SUBDIR, str(os.getpid()))
    try:
        os.makedirs(subdir)
    except OSError:
        pass
    # create file handler which logs even debug messages
    logfilename = os.path.join(subdir, '%s.log' % name)
    #logfilename = ''.join([name, '.log'])
    #logger.debug('Log in %s' % logfilename)
    fh = logging.FileHandler(logfilename)
    fh.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s %(process)d %(name)s %(levelname)s %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger

logger = getLogger(__file__)


SEP = '|'
SYSTEM_NAME = 'wifi'
HOUR_LENGTH = len('2013-05-18T19')
DAY_LENGTH = len('2013-05-18')
SCHED = Scheduler()


def join_args(*arg):
    return SEP.join(*arg)


def prefix(*arg):
    return join_args([SYSTEM_NAME, SEP.join(list(arg))])


def client(config=None):
    #logger.debug(dir(redis))
    if config and 'redis' in config:
        redis_config = config['redis']
        logger.debug('Using alternate Redis config %s' % (redis_config))
        return redis.Redis(
            host=redis_config['host'],
            port=int(redis_config['port']))
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
        self.assoclist_mac_set = prefix('assoclist')
        self.active_mac_set = prefix('active')
        self.mac_to_count_hash = prefix('count')
        self.mac_to_ip_hash = prefix('ip')
        self.mac_to_hostname_hash = prefix('hostname')
        self.ping_counter_key = prefix('ping')
        self.last_timestamp_key = prefix('last')

        self.left_mac_by_timestamp_z = prefix('left-by-timestamp')
        self.join_mac_by_timestamp_z = prefix('join-by-timestamp')

        self.excluded_mac_set = prefix('excluded')
        self.hour_set = prefix('hour')
        self.oui_to_manufacturer_hash = 'oui'
        self.started = time.time()

    def add_ip(self, mac, ip):
        self.r.hset(self.mac_to_ip_hash, mac, ip)

    def add_hostname(self, mac, hostname):
        self.r.hset(self.mac_to_hostname_hash, mac, hostname)

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

    def bulk(self, macs):
        m = self.r.pipeline()
        m.delete(self.assoclist_mac_set)
        m.sadd(self.assoclist_mac_set, *macs)
        m.execute()
        m.sdiff(self.assoclist_mac_set, self.active_mac_set)
        m.sdiff(self.active_mac_set, self.assoclist_mac_set)
        results = m.execute()

        joined_macs = results[0]
        left_macs = results[1]
        for mac in joined_macs:
            logger.info('Joining %s' % mac)
            self.join(mac)
        for mac in left_macs:
            logger.info('Leaving %s' % mac)
            self.left(mac)
        return (joined_macs, left_macs)

    def join(self, mac, interval=60*60):
        mac = mac.upper()
        if self.r.sismember(self.active_mac_set, mac):
            return False
        now = time.time()

        m = self.r.pipeline()
        m.sadd(self.active_mac_set, mac)
        m.hincrby(self.mac_to_count_hash, mac, 1)
        # only change last join timestamp if the MAC has been away long enough
        if not self._is_recently_active(mac, now, interval):
            m.zadd(self.join_mac_by_timestamp_z, mac, now)
            m.publish(prefix('join'), mac)
        if not self.r.sismember(self.excluded_mac_set, mac):
            m.hincrby(self.hour_set, hour(now), 1)
        m.execute()

        return True

    def left(self, mac):
        mac = mac.upper()
        if not self.r.sismember(self.active_mac_set, mac):
            # not joined...
            return False
        m = self.r.pipeline()
        m.srem(self.active_mac_set, mac)
        m.zadd(self.left_mac_by_timestamp_z, mac, time.time())
        m.srem(self.excluded_mac_set, mac)
        m.publish(prefix('left'), mac)
        m.execute()
        return True

    def purge(self, mac):
        mac = mac.upper()
        m = self.r.pipeline()
        m.hdel(self.mac_to_count_hash, mac)
        m.srem(self.active_mac_set, mac)
        m.srem(self.excluded_mac_set, mac)
        m.zrem(self.join_mac_by_timestamp_z, mac)
        m.zrem(self.left_mac_by_timestamp_z, mac)
        m.hdel(self.mac_to_ip_hash, mac)
        m.hdel(self.mac_to_hostname_hash, mac)
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
        results = self.r.zrangebyscore(
            self.join_mac_by_timestamp_z,
            start, end)
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

    def update_excluded(self, max_uptime=60*60*8):
        excluded = []
        for (mac_id, mac_info) in self.macs()['mac'].iteritems():
            if mac_info['uptime'] > max_uptime:
                self.r.sadd(self.excluded_mac_set, mac_id)
                self.r.publish(prefix('exclude'), mac_id)
                excluded.append(mac_id)
        return excluded

    def _is_recently_active(self, mac, now, interval):
        last_join = safe_float(self.r.zscore(
            self.left_mac_by_timestamp_z, mac))
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
        info['joined_iso8601'] = unix_to_iso8601(info['joined'])
        info['left_iso8601'] = unix_to_iso8601(info['left'])
        info['uptime'] = uptime
        return info

    def _fetch_mac(self, mac):
        oui = mac[0:8]
        m = self.r.pipeline()
        m.zscore(self.join_mac_by_timestamp_z, mac)
        m.hget(self.mac_to_count_hash, mac)
        m.hget(self.oui_to_manufacturer_hash, oui)
        m.zscore(self.left_mac_by_timestamp_z, mac)
        m.hget(self.mac_to_ip_hash, mac)
        m.hget(self.mac_to_hostname_hash, mac)
        results = m.execute()
        return {
            'joined': float(results[0]),
            'count': int(results[1]),
            'oui': results[2],
            'left': safe_float(results[3]),
            'ip': results[4],
            'hostname': results[5],
        }

    def _active(self):
        return self.r.sdiff(self.active_mac_set, self.excluded_mac_set)

    def _excluded(self):
        return self.r.smembers(self.excluded_mac_set)

    def _last(self):
        return safe_float(self.r.get(self.last_timestamp_key))


MAC_REGEXP = '\w{2}:\w{2}:\w{2}:\w{2}:\w{2}:\w{2}'
IP_REGEXP = '\d+\.\d+\.\d+\.\d+'
HOSTNAME_REGEXP = '[\w\*-]+'

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


#@get('/MAC/%s' % MAC_PATH)
#def join(mac):
#    DATA.join(mac)


@get('/MAC')
def macs():
    response.headers['Content-Type'] = 'text/json'
    return json.dumps(DATA.macs())


@get('/MAC/count')
def count():
    response.headers['Content-Type'] = 'text/plain'
    return '%s' % DATA.count()


@get('/MAC/excluded')
def excluded():
    response.headers['Content-Type'] = 'text/json'
    return json.dumps(DATA.excluded())


# @delete('/MAC/%s' % MAC_PATH)
# def left(mac):
#     DATA.left(mac)


@delete('/MAC/purge/%s' % MAC_PATH)
def purge(mac):
    DATA.purge(mac)


@get('/MAC/<start:re:[\.\d]*>/<end:re:[\.\d]*>')
def macs(start, end):
    response.headers['Content-Type'] = 'text/json'
    return json.dumps(DATA.query(start, end))


@SCHED.interval_schedule(minutes=1, coalesce=True)
def update_excluded():
    excluded = DATA.update_excluded()
    if len(excluded):
        logger.info('Refreshing update excluded: %s' % excluded)


@SCHED.interval_schedule(minutes=1, coalesce=True)
def update_leases():
    content = file(LEASES_FILENAME).read()
    regexp = '(%s) (%s) (%s)' % (MAC_REGEXP, IP_REGEXP, HOSTNAME_REGEXP)
    results = re.findall(regexp, content)
    logger.debug('Updating leases: %s' % results)
    for (mac, ip, hostname) in results:
        mac = mac.upper()
        DATA.add_ip(mac, ip)
        DATA.add_hostname(mac, hostname)


@SCHED.interval_schedule(minutes=1, coalesce=True)
def update_macs():
    content = file(ASSOCLIST_FILENAME).read()
    regexp = 'assoclist (%s)' % (MAC_REGEXP)
    results = re.findall(regexp, content)
    joined, left = DATA.bulk(results)
    logger.debug('Updated macs (joined, left) (%s,%s)' % (joined, left))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Capture wifi data')
    parser.add_argument(
        '-leases',
        dest='leases',
        default='/home/router/dnsmasq.leases')
    parser.add_argument(
        '-assoclist',
        dest='assoclist',
        default='/home/router/assoclist')
    args = parser.parse_args()

    if not os.path.isfile(args.leases):
        logger.debug('Not a file: %s' % args.leases)
        exit(1)

    global DATA, OPEN_IMAGE, CLOSE_IMAGE, LEASES_FILENAME, ASSOCLIST_FILENAME
    ASSOCLIST_FILENAME = args.assoclist
    LEASES_FILENAME = args.leases
    OPEN_IMAGE = get_file_content('xcj_open_badge.gif')
    CLOSE_IMAGE = get_file_content('xcj_closed_badge.gif')

    DATA = WifiData(client())

    update_macs()
    update_leases()
    update_excluded()

    SCHED.start()
    SCHED.print_jobs()

    logger.info('Starting API server')
    run(host='0.0.0.0', reloader=True, port=9000, debug=True)
