from defusedxml import ElementTree as DefusedElementTree
from defusedxml.minidom import parseString as defused_parse_string
from xml.etree import ElementTree

from je_web_runner.utils.exception.exception_tags import cant_read_xml_error
from je_web_runner.utils.exception.exception_tags import xml_type_error
from je_web_runner.utils.exception.exceptions import XMLException
from je_web_runner.utils.exception.exceptions import XMLTypeException


def reformat_xml_file(xml_string: str) -> str:
    """
    將 XML 字串重新排版 (pretty print)
    Reformat XML string into pretty-printed format

    :param xml_string: 原始 XML 字串 / raw XML string
    :return: 格式化後的 XML 字串 / pretty-printed XML string
    """
    dom = defused_parse_string(xml_string)
    return dom.toprettyxml()


class XMLParser(object):
    """
    XML 解析器
    XML Parser that supports parsing from string or file
    """

    def __init__(self, xml_string: str, xml_type: str = "string"):
        """
        初始化 XMLParser
        Initialize XMLParser

        :param xml_string: XML 字串或檔案路徑 / XML string or file path
        :param xml_type: "file" 或 "string" / "file" or "string"
        """
        self.tree = None
        self.xml_root = None
        self.xml_from_type = "string"
        self.xml_string = xml_string.strip()

        xml_type = xml_type.lower()
        if xml_type not in ["file", "string"]:
            raise XMLTypeException(xml_type_error)

        if xml_type == "string":
            self.xml_parser_from_string()
        else:
            self.xml_parser_from_file()

    def xml_parser_from_string(self, **kwargs) -> ElementTree.Element:
        """
        從字串解析 XML
        Parse XML from string

        :param kwargs: 額外參數傳給 defusedxml.ElementTree.fromstring
        :return: XML 根節點 / XML root element
        """
        try:
            self.xml_root = DefusedElementTree.fromstring(self.xml_string, **kwargs)
        except DefusedElementTree.ParseError as error:
            raise XMLException(cant_read_xml_error) from error
        return self.xml_root

    def xml_parser_from_file(self, **kwargs) -> ElementTree.Element:
        """
        從檔案解析 XML
        Parse XML from file

        :param kwargs: 額外參數傳給 defusedxml.ElementTree.parse
        :return: XML 根節點 / XML root element
        """
        try:
            self.tree = DefusedElementTree.parse(self.xml_string, **kwargs)
        except DefusedElementTree.ParseError as error:
            raise XMLException(cant_read_xml_error) from error
        self.xml_root = self.tree.getroot()
        self.xml_from_type = "file"
        return self.xml_root

    def write_xml(self, write_xml_filename: str, write_content: str):
        """
        將 XML 字串寫入檔案
        Write XML string into file

        :param write_xml_filename: 輸出檔案名稱 / output file name
        :param write_content: XML 內容字串 / XML content string
        """
        write_content = write_content.strip()
        content = DefusedElementTree.fromstring(write_content)
        tree = ElementTree.ElementTree(content)
        tree.write(write_xml_filename, encoding="utf-8")
