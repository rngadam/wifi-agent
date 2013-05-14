deployment:

* agent: xinchejian@burty.xinchejian.com
* server: xinchejian@vps2.xinchejian.com

# requirements

apt-get install python-redis
apt-get install python-pip
sudo pip install bottle

# Install

```
wget --no-check-certificate https://standards.ieee.org/develop/regauth/oui/oui.txt
./oui-loader.py
```

# agent

* edit router.passwd
*
```
./agent.sh
```

# api

```
./api.py
```

# testing

