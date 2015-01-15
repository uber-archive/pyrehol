from cStringIO import StringIO
from unittest import TestCase

from pyrehol import Pyrehol


class SmokeTestCase(TestCase):
    def test_basic(self):
        p = Pyrehol()
        p.leader_lines.append('sysctl -w net.nf_conntrack_max=10')
        eth0 = p.add_interface('foobar', 'eth0')
        eth0.set_protection('strong')
        eth0.set_policy('reject')
        g = eth0.add_group('src 127.0.0.1')
        g.set_policy('accept')
        g.add_server('smtp', 'accept')
        g = eth0.add_group('src 10.0.0.0/8')
        s = StringIO()
        p.emit(s)
        expected = """version 5

sysctl -w net.nf_conntrack_max=10

interface "eth0" foobar
  protection strong
  policy reject
  group with src 127.0.0.1
    policy accept
    server smtp accept
  group end

"""
        self.assertMultiLineEqual(expected, s.getvalue())
