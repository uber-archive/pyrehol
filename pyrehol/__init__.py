from __future__ import absolute_import

import cStringIO
import types

__name__ = 'pyrehol'
__author__ = 'James Brown <jbrown@uber.com>'
version_info = (0, 2)
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
    'mysql', 'netbackup', 'nfs', 'nntp', 'nntps', 'ntp', 'nut', 'nxserver', 'openvpn',
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


def nameify(name):
    if name is None:
        return
    assert '-' not in name, 'Name may not contain the "-" characeter'
    assert len(name) < 28, 'For dumb reasons, iptables varibales must be < 28 chars'


class Pyrehol(object):
    """Top-level wrapper for a Firehol config"""
    def __init__(self):
        self.contents = []
        self.service_defines = {}
        self.services = set(PREDEFINED_SERVICES)
        self.version = 5
        self.leader_lines = []
        self.trailer_lines = []

    def emit(self, out_fo=None):
        """Write out to a file descriptor. If one isn't passed, prints to standard out.

        :param out_fo: A file-like object or None
        """
        print_it = False
        if out_fo is None:
            out_fo = cStringIO.StringIO()
            print_it = True
        out_fo.write('version %d\n\n' % self.version)
        if self.leader_lines:
            out_fo.write('\n'.join(self.leader_lines))
            out_fo.write('\n\n')
        for thing in sorted(self.service_defines.values()):
            thing.emit(out_fo)
            out_fo.write('\n')
        for thing in self.contents:
            thing.emit(out_fo)
            out_fo.write('\n')
        if self.trailer_lines:
            out_fo.write('\n'.join(self.trailer_lines))
            out_fo.write('\n\n')
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
                if cls_obj._is_setter:
                    function_name = 'set_%s' % cls_obj.label
                else:
                    function_name = 'add_%s' % cls_obj.label
                if not getattr(kls, function_name, None):
                    def add_thing(self, *args, **kwargs):
                        if isinstance(self, Pyrehol):
                            kwargs['root'] = self
                        else:
                            kwargs['root'] = self.root
                        if cls_obj._is_setter and getattr(self, 'did_set_%s' % cls_obj.label, False):
                            raise ValueError('Cannot set %s on the same block more than once' % cls_obj.label)
                        o = cls_obj(*args, **kwargs)
                        setattr(self, 'set_%s' % cls_obj.label, True)
                        self.contents.append(o)
                        return o
                    add_thing.__name__ = function_name
                    add_thing.__doc__ = '%s %s on this %s. Returns the %s.\n\n' % (
                        'Set the' if cls_obj._is_setter else 'Add a new',
                        cls_obj.label, kls.__name__, name.replace('_', '', 1),
                    )
                    if cls_obj.__init__.__doc__:
                        add_thing.__doc__ += cls_obj.__init__.__doc__
                    setattr(kls, function_name, types.UnboundMethodType(add_thing, None, kls))
        return cls_obj


class _PyreholObject(object):
    __metaclass__ = _PyreholChainable
    _addable_from = tuple()
    _is_setter = False
    label = None

    def __init__(self, root=None):
        self.root = root

    def _w(self, file_object, indent, line):
        file_object.write(INDENT_CHAR * indent + line + '\n')

    def emit(self, fo):
        for indent, line in self.lines:
            self._w(fo, indent, line)


class _PyreholBlock(_PyreholObject):
    def __init__(self, name, root=None):
        super(_PyreholBlock, self).__init__(root=root)
        nameify(name)
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

    def __init__(self, name, root=None):
        super(_PyreholTopLevelBlock, self).__init__(name, root=root)
        self._before_name = ''
        self._after_name = ''

    @property
    def lines(self):
        yield (0, '%s%s%s %s%s%s' % (
            self.label,
            ' ' if self._before_name else '', self._before_name,
            self.name,
            ' ' if self._after_name else '', self._after_name
        ))
        for line in super(_PyreholTopLevelBlock, self).lines:
            yield line


class _PyreholRouter(_PyreholTopLevelBlock):
    label = 'router'

    def __init__(self, name, rule_params, root=None):
        """Construct a router block

        :param name: Name of this block. Should be suitable to use as a bash variable name
        :param rule_params: A list of rule paramters (e.g., "inface eth0" or "src 10.0.0.0/8")
        """
        super(_PyreholInterface, self).__init__(name, root=root)
        self.rule_params = listify(rule_params)
        self._after_name = ' '.join(self.rule_params)


class _PyreholInterface(_PyreholTopLevelBlock):
    label = 'interface'

    def __init__(self, name, interfaces, root=None):
        """Construct an interface block

        :param name: Name of this block. Should be suitable to use as a bash variable name
        :param interfaces: List of interface devices (e.g., "eth0")
        """
        super(_PyreholInterface, self).__init__(name, root=root)
        self.interfaces = listify(interfaces)
        self._before_name = '"%s"' % ' '.join(self.interfaces)


class _PyreholGroup(_PyreholBlock):
    _addable_from = (_PyreholBlock,)
    label = 'group'

    def __init__(self, rule_params, root=None):
        """An arbitrary grouping of rules, for efficiency

        :param rule_params: A list of mutating parameters to group by (e.g., "src 10.0.0.0/8")
        """
        super(_PyreholGroup, self).__init__(name=None, root=root)
        self.rule_params = listify(rule_params)

    @property
    def lines(self):
        if not self.contents:
            return
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
    _is_setter = True

    def __init__(self, action, root=None):
        """Set the default policy for this block.

        :param action: The default action to take (accept, drop, reject, etc.)
        """
        super(_PyreholPolicy, self).__init__(root=root)
        self.text = '%s %s' % (self.label, action)


class _PyreholService(_PyreholStanza):
    _addable_from = (Pyrehol,)

    def __init__(self, name, server_portspec, client_portspec, root=None):
        """A single service

        :param name: A name suitable for use as a bash variable name
        :param server_portspec: Server portspec (e.g., "tcp/80")
        :param client_portspec: Client portspec (e.g., "default")
        """
        super(_PyreholService, self).__init__(root=root)
        nameify(name)
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
        """A server stanza. For communication INPUT to this host.

        :param services: Service name or list of service names (e.g., "http")
        :param action: Action to take for these services (e.g., "accept")
        :param rule_params: A list of modifying rule parameters (e.g, "src 10.0.0.0/8")
        """
        super(_PyreholServer, self).__init__(root=root)
        services = listify(services)
        for service in services:
            assert service in self.root.services, \
                '%s not defined (missing .define_service call?)' % service
        self.text = '%s %s%s%s %s%s%s' % (
            self.label,
            '"' if len(services) > 1 else '',
            ' '.join(services),
            '"' if len(services) > 1 else '',
            action,
            ' ' if rule_params else '',
            ' '.join(rule_params),
        )


class _PyreholClient(_PyreholStanza):
    label = 'client'

    def __init__(self, services, action, rule_params=[], root=None):
        """A client stanza. For communication OUTPUT from this host.

        :param services: Service name or list of service names (e.g., "http")
        :param action: Action to take for these services (e.g., "accept")
        :param rule_params: A list of modifying rule parameters (e.g, "src 10.0.0.0/8")
        """
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
    _is_setter = True

    def __init__(self, protection_level, root=None):
        """The flood/invalid packet protection level for this block

        :param protection_level: http://firehol.org/firehol-manual/firehol-protection/
        """
        super(_PyreholProtection, self).__init__(root=root)
        self.text = '%s %s' % (self.label, protection_level)
