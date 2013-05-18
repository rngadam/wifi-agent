#!/usr/bin/env python
import urllib
import json
import httplib
import argparse

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

def join(args):
    return client.join(args.mac)

def left(args):
    return client.left(args.mac)

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

    left_parser = subparsers.add_parser('left', help='left MAC')
    left_parser.add_argument('mac', help='mac address')
    left_parser.set_defaults(func=left)

    count_parser = subparsers.add_parser('count', help='count MAC')
    count_parser.set_defaults(func=count)

    list_parser = subparsers.add_parser('list', help='list MAC')
    list_parser.set_defaults(func=list_macs)

    excluded_list_parser = subparsers.add_parser('excluded', help='excluded MAC')
    excluded_list_parser.set_defaults(func=excluded_list_macs)

    agent_parser = subparsers.add_parser('agent', help='agent')
    agent_parser.set_defaults(func=agent)

    ping_parser = subparsers.add_parser('ping', help='ping MAC')
    ping_parser.set_defaults(func=ping)

    args = parser.parse_args()

    global client
    client = Client(args.hostname, args.port)

    print args.func(args)