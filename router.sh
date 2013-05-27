#!/bin/sh
wl_atheros assoclist > ~/assoclist
scp -i ~/.ssh/id_rsa.db /tmp/dnsmasq.leases $HOME/assoclist router@vps2.xinchejian.com:
