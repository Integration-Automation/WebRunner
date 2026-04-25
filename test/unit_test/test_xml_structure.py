import unittest
from typing import Any, cast

from defusedxml.ElementTree import fromstring

from je_web_runner.utils.xml.change_xml_structure.change_xml_structure import (
    dict_to_elements_tree,
    elements_tree_to_dict,
)


class TestXmlStructure(unittest.TestCase):

    def test_dict_to_xml_simple(self):
        data = {"root": {"child": "value"}}
        xml_str = dict_to_elements_tree(data)
        self.assertIn("<root>", xml_str)
        self.assertIn("<child>value</child>", xml_str)
        self.assertIn("</root>", xml_str)

    def test_dict_to_xml_nested(self):
        data = {"root": {"parent": {"child": "val"}}}
        xml_str = dict_to_elements_tree(data)
        self.assertIn("<parent>", xml_str)
        self.assertIn("<child>val</child>", xml_str)

    def test_dict_to_xml_with_list(self):
        data = {"root": {"item": ["a", "b", "c"]}}
        xml_str = dict_to_elements_tree(data)
        self.assertEqual(xml_str.count("<item>"), 3)

    def test_roundtrip(self):
        data = {"root": {"name": "test", "value": "123"}}
        xml_str = dict_to_elements_tree(data)
        tree = fromstring(xml_str)
        result = elements_tree_to_dict(tree)
        self.assertEqual(result["root"]["name"], "test")
        self.assertEqual(result["root"]["value"], "123")

    def test_invalid_type_raises(self):
        bad_input: Any = "not a dict"
        with self.assertRaises(TypeError):
            dict_to_elements_tree(cast(dict, bad_input))

    def test_multiple_root_keys_raises(self):
        with self.assertRaises(ValueError):
            dict_to_elements_tree({"root1": {}, "root2": {}})


if __name__ == "__main__":
    unittest.main()
