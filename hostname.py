#!/usr/bin/env python

import re
import socket
import sh

def lookup(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except socket.herror:
        return None

# fill up the cache
#sh.nmap('-sP', '10.0.10.*')
# read the arp table
arp = file('/proc/net/arp').read()
# parse
ip_mac = re.findall("([\d\.]*) .* (\w{2}:\w{2}:\w{2}:\w{2}:\w{2}:\w{2})", arp)
# lookup
filtered = [(im[0], im[1], lookup(im[0])) for im in ip_mac if im[1] != '00:00:00:00:00:00']
print filtered