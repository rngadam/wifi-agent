#!/usr/bin/env python

import sys
import redis

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print 'Usage: <redis hash key> <redis zset key>'
        exit(1)
    r = redis.Redis()
    hash_set = sys.argv[1]
    z_set = sys.argv[2]
    print "from hash %s -> zset %s" % (hash_set, z_set)
    kv = r.hgetall(hash_set)
    print kv
    for (member, score) in kv.iteritems():
        print "%s='%s' %s" % (member, score, type(score))
        r.zadd(z_set, member, score)