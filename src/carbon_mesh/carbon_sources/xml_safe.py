"""Safe XML parsing for untrusted upstream responses.

Grid-operator XML (ENTSO-E, IESO, ...) is parsed straight from the network, so
use defusedxml to disable external entity resolution and entity-expansion
(billion-laughs) -- defense in depth in case a source is compromised or spoofed.
The returned element is a standard ElementTree Element, so callers are unchanged.
"""

from xml.etree.ElementTree import Element

from defusedxml.ElementTree import fromstring as _fromstring


def parse_xml(data: str | bytes) -> Element:
    return _fromstring(data)
