#!/usr/bin/env python
import urllib
import json
import httplib
import argparse
import dateutil.parser
import datetime
import time

class Client():

    def __init__(self, hostname=None, port=None, protocol='http'):
        self.hostname = hostname
        self.port = port
        self.protocol = protocol

    def _delete(self, uri):
        conn = httplib.HTTPConnection(self.hostname, self.port)
        conn.request('DELETE', uri)
        resp = conn.getresponse()
        content = resp.read()
        return content

    def _url(self, uri):
        return "%s://%s:%s%s" % (self.protocol, self.hostname, self.port, uri)

    def _get(self, uri):
        url = self._url(uri)
        f = urllib.urlopen(url)
        output = f.read()
        return output

    def join(self, mac):
        if mac is object:
            mac = mac.mac
        uri = '/MAC/%s' % mac
        return self._get(uri)

    def left(self, mac):
        if mac is object:
            mac = mac.mac
        uri = '/MAC/%s' % mac
        return self._delete(uri)

    def purge(self, mac):
        uri = '/MAC/purge/%s' % mac
        return self._delete(uri)

    def count(self):
        uri = '/MAC/count'
        return self._get(uri)

    def excluded(self):
        uri = '/MAC/excluded'
        return self._get(uri)

    def macs(self):
        uri = '/MAC'
        return self._get(uri)

    def agent(self):
        uri = '/agent'
        return self._get(uri)

    def ping(self):
        uri = '/ping'
        return self._get(uri)

    def query(self, start_timestamp, end_timestamp):
        uri = '/MAC/%s/%s' % (start_timestamp, end_timestamp)
        return self._get(uri)

def from_timestamp_to_date(u):
    return datetime.datetime.utcfromtimestamp(u)

def from_date_to_timestamp(d):
    return time.mktime(d.timetuple())

def join(args):
    return client.join(args.mac)

def query(args):
    start_date = dateutil.parser.parse(args.start)
    end_date = dateutil.parser.parse(args.end)
    start_timestamp = from_date_to_timestamp(start_date)
    end_timestamp = from_date_to_timestamp(end_date)
    print 'from: %s (%s) to %s (%s)' % (start_date, start_timestamp, end_date, end_timestamp)
    return client.query(start_timestamp, end_timestamp)

def left(args):
    return client.left(args.mac)

def purge(args):
    return client.purge(args.mac)

def list_macs(args):
    return client.macs()

def agent(args):
    return client.agent()

def count(args):
    return client.count()

def ping(args):
    return client.ping()

def excluded_list_macs(args):
    return client.excluded()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-hostname',
        default='vps2.xinchejian.com',
        help='hostname for API')
    parser.add_argument(
        '-port',
        default='9000',
        help='port for API')

    subparsers = parser.add_subparsers()


    join_parser = subparsers.add_parser('join', help='join MAC')
    join_parser.add_argument('mac', help='mac address')
    join_parser.set_defaults(func=join)

    query_parser = subparsers.add_parser('query', help='query MAC')
    query_parser.add_argument('start', help='start timestamp')
    query_parser.add_argument('end', help='end timestamp')
    query_parser.set_defaults(func=query)

    left_parser = subparsers.add_parser('left', help='left MAC')
    left_parser.add_argument('mac', help='mac address')
    left_parser.set_defaults(func=left)

    purge_parser = subparsers.add_parser('purge', help='purge MAC')
    purge_parser.add_argument('mac', help='mac address')
    purge_parser.set_defaults(func=purge)

    count_parser = subparsers.add_parser('count', help='count MAC')
    count_parser.set_defaults(func=count)

    list_parser = subparsers.add_parser('list', help='list MAC')
    list_parser.set_defaults(func=list_macs)

    excluded_list_parser = subparsers.add_parser('excluded', help='excluded MAC')
    excluded_list_parser.set_defaults(func=excluded_list_macs)

    agent_parser = subparsers.add_parser('agent', help='agent information')
    agent_parser.set_defaults(func=agent)

    ping_parser = subparsers.add_parser('ping', help='ping agent')
    ping_parser.set_defaults(func=ping)

    args = parser.parse_args()

    global client
    client = Client(args.hostname, args.port)

    print args.func(args)