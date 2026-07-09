"""Unit tests for the XML parser/writer helpers (xml.xml_file.xml_file)."""
import pytest

from je_web_runner.utils.exception.exceptions import XMLException, XMLTypeException
from je_web_runner.utils.xml.xml_file.xml_file import XMLParser, reformat_xml_file


def test_reformat_xml_pretty_prints():
    result = reformat_xml_file("<root><child>x</child></root>")
    assert "<root>" in result  # nosec B101
    assert "<child>" in result  # nosec B101
    # toprettyxml() inserts newlines between elements.
    assert "\n" in result  # nosec B101


def test_xml_parser_from_string_returns_root():
    parser = XMLParser("<root><a>1</a></root>")
    assert parser.xml_root.tag == "root"  # nosec B101
    assert parser.xml_from_type == "string"  # nosec B101
    assert parser.xml_root.find("a").text == "1"  # nosec B101


def test_xml_parser_invalid_type_raises():
    with pytest.raises(XMLTypeException):
        XMLParser("<root/>", xml_type="bogus")


def test_xml_parser_invalid_xml_raises():
    with pytest.raises(XMLException):
        XMLParser("<root><a></root>", xml_type="string")


def test_xml_parser_from_file_round_trip(tmp_path):
    target = tmp_path / "out.xml"
    XMLParser("<root/>").write_xml(str(target), "<data><item>1</item></data>")
    assert target.exists()  # nosec B101

    parser = XMLParser(str(target), xml_type="file")
    assert parser.xml_root.tag == "data"  # nosec B101
    assert parser.xml_from_type == "file"  # nosec B101
    assert parser.xml_root.find("item").text == "1"  # nosec B101


def test_xml_parser_from_file_invalid_raises(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text("<root><a></root>", encoding="utf-8")
    with pytest.raises(XMLException):
        XMLParser(str(bad), xml_type="file")
