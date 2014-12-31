[![Build Status](https://travis-ci.org/uber/pyrehol.svg)](https://travis-ci.org/uber/pyrehol)

**pyrehol** is a python library for generating [FireHOL](http://firehol.org) config files. It's perfect if you want to combine the human-readable, reproductable, and reliable nature of FireHOL with some kind of automated cluster management system (for example, [clusto](http://clusto.org)) without having to write super-complicated Bash.

### Usage
```python
from pyrehol import Pyrehol
from somewhere_else import clusto


my_clusto_object = clusto.get_by_name(socket.gethostname())

p = Pyrehol()
with p.add_interface("public", "eth0") as i:
    i.set_protection('strong')
    for service in my_clusto_object.attr_values(key='firehol', subkey='allowed-services'):
        i.add_server(service, 'accept')

with p.add_interface("private", "eth1") as i:
    i.add_server('ssh', 'accept')

with open('/etc/firehol/firehol.conf', 'w') as f:
    p.emit(f)
```


### License
This software is Copyright &copy; 2014 Uber Technologies, Inc.

This software is licensed under the Expat (MIT) license. More information can be found in [LICENSE.txt]().


### FAQ

#### When is FireHOL 2.0 support coming?
Real soon now
