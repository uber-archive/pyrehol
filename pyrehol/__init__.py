from __future__ import absolute_import

import cStringIO
import decorator

__name__ = 'pyrehol'
__author__ = 'James Brown <jbrown@uber.com>'
version_info = (0, 1)
__version__ = '.'.join(map(str, version_info))

INDENT_CHAR = '  '

PREDEFINED_SERVICES = frozenset([
    'any', 'anystateless', 'all',
    'AH', 'apcupsd', 'apcupsdnis', 'aptproxy', 'asterisk', 'cups',
    'cvspserver', 'darkstat', 'daytime', 'dcc', 'dcpp', 'dhcprelay', 'dict',
    'distcc', 'dns', 'echo', 'eserver', 'ESP', 'finger', 'gift', 'giftui',
    'gkrellmd', 'GRE', 'h323', 'heartbeat', 'http', 'https', 'iax', 'iax2',
    'icmp', 'ICMP', 'icp', 'ident', 'imap', 'imaps', 'irc', 'isakmp',
    'jabber', 'jabberd', 'ldap', 'ldaps', 'lpd', 'mms', 'msn', 'msnp',
    'mysql', 'netbackup', 'nntp', 'nntps', 'ntp', 'nut', 'nxserver', 'openvpn',
    'oracle', 'OSPF', 'pop3', 'pop3s', 'portmap', 'postgres', 'privoxy',
    'radius', 'radiusold', 'radiusoldproxy', 'radiusproxy', 'rdp', 'rndc',
    'rsync', 'rtp', 'sip', 'smtp', 'smtps', 'snmp', 'snmptrap', 'socks',
    'squid', 'ssh', 'stun', 'submission', 'sunrpc', 'swat', 'syslog', 'telnet',
    'time', 'upnp', 'uucp', 'vmware', 'vmwareauth', 'vmwareweb', 'vnc',
    'webcache', 'webmin', 'whois', 'xdmcp',
])


def listify(string_or_list):
    if isinstance(string_or_list, basestring):
        return [string_or_list]
    else:
        return string_or_list


class Pyrehol(object):
    """Top-level wrapper for a Firehol config"""
    def __init__(self):
        self.contents = []
        self.service_defines = {}
        self.services = set(PREDEFINED_SERVICES)
        self.version = 5

    def emit(self, out_fo=None):
        print_it = False
        if out_fo is None:
            out_fo = cStringIO.StringIO()
            print_it = True
        out_fo.write('version %d\n\n' % self.version)
        for thing in sorted(self.service_defines.values()):
            thing.emit(out_fo)
            out_fo.write('\n')
        for thing in self.contents:
            thing.emit(out_fo)
            out_fo.write('\n')
        if print_it:
            print out_fo.getvalue()

    def define_service(self, service_name, server_portspec,
                       client_portspec='default'):
        """Add a new service to Firehol (for use in server/client blocks later).

        :param service_name: Name for the service, suitable for use as a bash variable name
        :param server_portspec: Port specification for the server side (example: "tcp/80 tcp/443")
        :param client_portspec: Port specification for the client side (example: "any")
        """
        new_define = _PyreholService(
            service_name, server_portspec, client_portspec, root=self
        )
        if service_name in self.services:
            assert new_define == self.service_defines[service_name],\
                '%s != %s' % (new_define, self.service_defines[service_name])
        else:
            self.service_defines[service_name] = new_define
        self.services.add(service_name)


class _PyreholChainable(type):
    def __new__(cls, name, bases, dct):
        cls_obj = type.__new__(cls, name, bases, dct)
        if cls_obj.label is not None:
            for kls in cls_obj._addable_from:
                function_name = 'add_%s' % cls_obj.label
                if not getattr(kls, function_name, None):
                    @decorator.decorator
                    def add_thing(self, *args, **kwargs):
                        if isinstance(self, Pyrehol):
                            kwargs['root'] = self
                        else:
                            kwargs['root'] = self.root
                        o = cls_obj(*args, **kwargs)
                        self.contents.append(o)
                        return o
                    add_thing.__name__ = function_name
                    add_thing.__doc__ = 'Add a new %s to this %s. Returns the %s' % (
                        cls_obj.label, kls.__name__, name.replace('_', '', 1)
                    )
                    setattr(kls, function_name, add_thing)
        return cls_obj


class _PyreholObject(object):
    __metaclass__ = _PyreholChainable
    _addable_from = tuple()
    label = None

    def __init__(self, root):
        self.root = root

    def _w(self, file_object, indent, line):
        file_object.write(INDENT_CHAR * indent + line + '\n')

    def emit(self, fo):
        for indent, line in self.lines:
            self._w(fo, indent, line)


class _PyreholBlock(_PyreholObject):
    def __init__(self, name, root):
        super(_PyreholBlock, self).__init__(root=root)
        self.name = name
        self.contents = []

    @property
    def lines(self):
        for thing in self.contents:
            for indent, line in thing.lines:
                yield indent + 1, line

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        return False


class _PyreholTopLevelBlock(_PyreholBlock):
    _addable_from = (Pyrehol,)

    def __init__(self, name, root):
        super(_PyreholTopLevelBlock, self).__init__(name, root=root)
        self._before_name = ''
        self._after_name = ''

    @property
    def lines(self):
        yield (0, '%s %s %s %s' % (
            self.label, self._before_name, self.name, self._after_name
        ))
        for line in super(_PyreholTopLevelBlock, self).lines:
            yield line


class _PyreholRouter(_PyreholTopLevelBlock):
    label = 'router'

    def __init__(self, name, rule_params, root):
        super(_PyreholInterface, self).__init__(name, root=root)
        self.rule_params = listify(rule_params)
        self._after_name = ' '.join(self.rule_params)


class _PyreholInterface(_PyreholTopLevelBlock):
    label = 'interface'

    def __init__(self, name, interfaces, root):
        super(_PyreholInterface, self).__init__(name, root=root)
        self.interfaces = listify(interfaces)
        self._before_name = '"%s"' % ' '.join(self.interfaces)


class _PyreholGroup(_PyreholBlock):
    _addable_from = (_PyreholBlock,)
    label = 'group'

    def __init__(self, rule_params, root):
        super(_PyreholGroup, self).__init__(name=None, root=root)
        self.rule_params = listify(rule_params)

    @property
    def lines(self):
        yield (0, 'group with %s' % ' '.join(self.rule_params))
        for thing in self.contents:
            for indent, line in thing.lines:
                yield indent + 1, line
        yield (0, 'group end')


class _PyreholStanza(_PyreholObject):
    _addable_from = (_PyreholBlock,)

    @property
    def lines(self):
        yield 0, self.text


class _PyreholPolicy(_PyreholStanza):
    label = 'policy'

    def __init__(self, action, root):
        super(_PyreholPolicy, self).__init__(root=root)
        self.text = '%s %s' % (self.label, action)


class _PyreholService(_PyreholStanza):
    _addable_from = (Pyrehol,)

    def __init__(self, name, server_portspec, client_portspec, root):
        super(_PyreholService, self).__init__(root=root)
        self.name = name
        self.server_portspec = tuple(sorted(listify(server_portspec)))
        self.client_portspec = tuple(sorted(listify(client_portspec)))

    @property
    def _tuple(self):
        return (self.name, self.server_portspec, self.client_portspec)

    def __cmp__(self, other):
        return cmp(self._tuple, other._tuple)

    def __repr__(self):
        return 'PyreholService(%s, %s, %s)' % (self.name, self.server_portspec, self.client_portspec)

    @property
    def lines(self):
        yield 0, 'server_%s_ports="%s"' % (
            self.name, ' '.join(self.server_portspec)
        )
        yield 0, 'client_%s_ports="%s"' % (
            self.name, ' '.join(self.client_portspec)
        )


class _PyreholServer(_PyreholStanza):
    label = 'server'

    def __init__(self, services, action, rule_params=[], root=None):
        super(_PyreholServer, self).__init__(root=root)
        services = listify(services)
        for service in services:
            assert service in self.root.services, \
                '%s not defined (missing .define_service call?)' % service
        self.text = '%s %s%s%s %s %s' % (
            self.label,
            '"' if len(services) > 1 else '',
            ' '.join(services),
            '"' if len(services) > 1 else '',
            action,
            ' '.join(rule_params),
        )


class _PyreholClient(_PyreholStanza):
    label = 'client'

    def __init__(self, services, action, rule_params=[], root=None):
        super(_PyreholClient, self).__init__(root=root)
        services = listify(services)
        for service in services:
            assert service in self.root.services, \
                '%s not defined (missing .define_service call?)' % service
        self.text = '%s %s%s%s %s %s' % (
            self.label,
            '"' if len(services) > 1 else '',
            ' '.join(services),
            '"' if len(services) > 1 else '',
            action,
            ' '.join(rule_params),
        )


class _PyreholProtection(_PyreholStanza):
    label = 'protection'

    def __init__(self, protection_level, root):
        super(_PyreholProtection, self).__init__(root=root)
        self.text = '%s %s' % (self.label, protection_level)


if __name__ == '__main__':
    p = Pyrehol()
    eth0 = p.add_interface('foobar', 'eth0')
    eth0.add_protection('strong')
    eth0.add_policy('reject')
    g = eth0.add_group('src 127.0.0.1')
    g.add_policy('accept')
    g.add_server('smtp', 'accept')
    g = eth0.add_group('src 10.0.0.0/8')
    p.emit()
