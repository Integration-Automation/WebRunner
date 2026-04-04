XML Utilities API
=================

``je_web_runner.utils.xml.xml_file.xml_file``

Class: XMLParser
----------------

.. code-block:: python

    class XMLParser:
        """
        XML parser that supports parsing from string or file.

        Attributes:
            element_tree: xml.etree.ElementTree module
            tree: parsed ElementTree
            xml_root: root Element of the parsed XML
            xml_from_type (str): source type ("string" or "file")
        """

        def __init__(self, xml_string: str, xml_type: str = "string"):
            """
            :param xml_string: XML content string or file path
            :param xml_type: "string" to parse from string, "file" to parse from file
            :raises XMLTypeException: if xml_type is not "string" or "file"
            """

        def xml_parser_from_string(self, **kwargs) -> Element:
            """
            Parse XML from a string.

            :return: root Element
            """

        def xml_parser_from_file(self, **kwargs) -> Element:
            """
            Parse XML from a file.

            :return: root Element
            """

Function: reformat_xml_file
---------------------------

.. code-block:: python

    def reformat_xml_file(xml_string: str) -> str:
        """
        Pretty-print an XML string with indentation.

        :param xml_string: XML string to format
        :return: formatted XML string
        """
