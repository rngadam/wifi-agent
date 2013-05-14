#!/usr/bin/env python

import re
import redis

pairs = {}
count = 0
for l in file('oui.txt').readlines():
    m = re.search('(\w{2})-(\w{2})-(\w{2}).*\(hex\)(.*)', l)
    if m:
        prefix = '%s:%s:%s' % (m.group(1), m.group(2), m.group(3))
        name = m.group(4).strip()
        print '%s %s %s' % (count, prefix, name)
        count = count + 1
        pairs[prefix] = name

print count

r = redis.Redis()
print r.hmset('oui', pairs)
