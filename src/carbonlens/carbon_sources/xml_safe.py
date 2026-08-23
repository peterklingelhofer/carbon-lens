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


def safe_parse_xml(data: str | bytes) -> Element | None:
    """parse_xml that swallows malformed input, returning None instead of raising.

    For feeds where a parse failure should degrade to "no data" rather than
    propagate an exception.
    """
    try:
        return _fromstring(data)
    except Exception:
        return None


def entsoe_ns(root: Element) -> dict[str, str]:
    """Namespace map for an ENTSO-E document, derived from the root tag.

    ENTSO-E documents declare their own URN as the default namespace (and it
    differs per document type), so read it off the root rather than hardcoding.
    """
    return {"ns": root.tag.split("}")[0].strip("{")}
