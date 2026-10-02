#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Where does a connection stop -- and is that a refusal or a stale record?

WHAT HAPPENED, dreamlandbbs.com, 2026-09-27 to 2026-10-02. Every request timed out at 21.2 s.
Three measurements across five days, all three written into the register as a rate-limit penalty:
"the host said so within a minute", "the timer is stable, so the rule behind it is untouched",
"not before the host has been left alone for days". The archive was treated as blocked and left
alone, and the reasoning offered for the diagnosis was that two readings with the same timer could
not be coincidence.

They were not a coincidence. A TCP connect to a CLOSED PORT times out on a fixed timer, which is
what made the readings agree, and agreement of a repeated experiment says nothing about its cause.
Separating the layers took one call:

    DNS: www.dreamlandbbs.com -> 62.163.18.65
    TCP 80:  timed out after 15.0s
    TCP 443: open in 0.0s

The host had closed port 80 and moved to HTTPS. The archive's base said `http://`, so every request
went to a shut door. 5 648 files and 14.05 GB were reachable the whole time.

AND IT SETTLES A TEMPTING WRONG ANSWER. A browser User-Agent was proposed twice during those five
days. A header cannot matter when the handshake never completes -- and `reach` is what shows that
instead of asserting it.

THE SAME INSTRUMENT ALSO SAYS WHEN A BLOCK IS REAL. openpa.net reads 80 shut AND 443 shut: that is
the host refusing an address, and `scheme_drift` returns None rather than inventing a scheme.

Everything here uses injected resolve/connect fakes. A probe that needed the network could not be
tested, and these are the readings that produced a wrong diagnosis in the first place.
"""
import os
import socket
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402


def fake(ip="192.0.2.1", shut=(), dns=None):
    """-> (resolve, connect) that answer as told. `shut` lists the ports that time out."""
    def resolve(host):
        if dns:
            raise socket.gaierror(-2, dns)
        return ip

    def connect(host, port, timeout):
        if port in shut:
            raise socket.timeout("timed out")

    return resolve, connect


class WhereTheConnectionStops(unittest.TestCase):

    def probe(self, **kw):
        resolve, connect = fake(**kw)
        return common.reach("a.host.invalid", resolve=resolve, connect=connect)

    def test_a_healthy_host_reads_clean(self):
        got = self.probe()
        self.assertIsNone(got["dns"])
        self.assertEqual(got["ports"], {80: None, 443: None})
        self.assertEqual(got["ip"], "192.0.2.1")

    def test_dns_failure_stops_before_the_ports(self):
        """No port is probed, and the absence is not reported as a closed port."""
        got = self.probe(dns="Name or service not known")
        self.assertIn("Name or service", got["dns"])
        self.assertEqual(got["ports"], {})

    def test_the_dreamlandbbs_reading(self):
        got = self.probe(shut=(80,))
        self.assertIsNone(got["dns"])
        self.assertIsNotNone(got["ports"][80])
        self.assertIsNone(got["ports"][443])

    def test_the_openpa_reading(self):
        """Both ports shut: the host is refusing this address, not moving scheme."""
        got = self.probe(shut=(80, 443))
        self.assertIsNotNone(got["ports"][80])
        self.assertIsNotNone(got["ports"][443])

    def test_an_error_with_no_text_still_reports_something(self):
        """A bare exception must not read as success -- None means "connected"."""
        def connect(host, port, timeout):
            raise socket.timeout()
        got = common.reach("h.invalid", resolve=lambda h: "192.0.2.1", connect=connect)
        self.assertTrue(got["ports"][80])
        self.assertTrue(got["ports"][443])

    def test_the_ports_asked_for_are_the_ports_reported(self):
        resolve, connect = fake(shut=(8080,))
        got = common.reach("h.invalid", ports=(8080, 8443), resolve=resolve, connect=connect)
        self.assertEqual(sorted(got["ports"]), [8080, 8443])


class AStaleRecordIsNotARefusal(unittest.TestCase):
    """scheme_drift: the distinction that cost five days of waiting for a block that was not there."""

    def drift(self, **kw):
        resolve, connect = fake(**kw)
        return common.scheme_drift(common.reach("h.invalid", resolve=resolve, connect=connect))

    def test_port_80_shut_and_443_open_means_the_site_wants_https(self):
        self.assertEqual(self.drift(shut=(80,)), "https")

    def test_the_reverse_is_also_read(self):
        """A site that dropped TLS, or whose certificate expired into a closed port."""
        self.assertEqual(self.drift(shut=(443,)), "http")

    def test_both_shut_is_NOT_a_drift(self):
        """THE CASE THAT MUST NOT BE GUESSED AT. This is openpa: the host refusing an address.
        Returning a scheme here would turn a real block into a configuration note."""
        self.assertIsNone(self.drift(shut=(80, 443)))

    def test_both_open_is_not_a_drift_either(self):
        self.assertIsNone(self.drift())

    def test_a_dns_failure_is_not_a_drift(self):
        """Nothing was learned about any port, so nothing may be concluded about a scheme."""
        self.assertIsNone(self.drift(dns="no such host"))

    def test_a_result_missing_a_port_yields_nothing(self):
        """Half a measurement is not a verdict."""
        self.assertIsNone(common.scheme_drift({"dns": None, "ports": {80: "timed out"}}))

    def test_it_is_exported_with_its_probe(self):
        self.assertIn("reach", common.__all__)
        self.assertIn("scheme_drift", common.__all__)


if __name__ == "__main__":
    unittest.main(verbosity=1)
