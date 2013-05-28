deployment:

* server: xinchejian@vps2.xinchejian.com

# requirements

apt-get install python-redis python-pip python-dateutil
sudo pip install bottle

# Server Install

```
wget --no-check-certificate https://standards.ieee.org/develop/regauth/oui/oui.txt
./oui-loader.py
```
Launch the API:

```
./api.py
```

# Router install

copy the router@vps2.xinchejian.com:.ssh/id_rsa to the router /tmp/root/.ssh directory

```
dropbearconvert openssh dropbear id_rsa id_rsa.db
ssh -i ~/.ssh/id_rsa.db router@vps2.xinchejian.com
```

copy router.sh to the /tmp/root/router.sh

Create crontab entry (/tmp/cron.d/router):

```
*      *       *       *       *       root /tmp/root/router.sh
```

Restart cron:

```
stopservice cron && startservice cron
```


# TODO

hincrby '%02d%02d' % (d.weekday(), d.hour)