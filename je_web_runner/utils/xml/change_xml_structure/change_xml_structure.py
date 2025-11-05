from collections import defaultdict
from xml.etree import ElementTree


def elements_tree_to_dict(elements_tree) -> dict:
    """
    將 XML ElementTree 轉換成 dict
    Convert XML ElementTree into a Python dict

    :param elements_tree: XML ElementTree 的根節點 / root element of XML tree
    :return: dict 格式的資料 / data as dict
    """
    # 初始化字典，若有屬性則用空 dict，否則為 None
    # Initialize dict: {} if element has attributes, else None
    elements_dict: dict = {elements_tree.tag: {} if elements_tree.attrib else None}

    # 取得子節點
    # Get children
    children: list = list(elements_tree)

    if children:
        # 使用 defaultdict(list) 來收集相同 tag 的子節點
        # Use defaultdict(list) to collect children with same tag
        default_dict = defaultdict(list)
        for dc in map(elements_tree_to_dict, children):
            for key, value in dc.items():
                default_dict[key].append(value)

        # 如果某個 tag 只有一個元素，直接取值；否則保留 list
        # If a tag has only one element, unwrap it; else keep as list
        elements_dict: dict = {
            elements_tree.tag: {
                key: value[0] if len(value) == 1 else value
                for key, value in default_dict.items()
            }
        }

    # 處理屬性 (加上 @ 前綴)
    # Handle attributes (prefix with @)
    if elements_tree.attrib:
        elements_dict[elements_tree.tag].update(
            ('@' + key, value) for key, value in elements_tree.attrib.items()
        )

    # 處理文字內容
    # Handle text content
    if elements_tree.text:
        text = elements_tree.text.strip()
        if children or elements_tree.attrib:
            if text:
                elements_dict[elements_tree.tag]['#text'] = text
        else:
            elements_dict[elements_tree.tag] = text

    return elements_dict


def dict_to_elements_tree(json_dict: dict) -> str:
    """
    將 dict 轉換成 XML 字串
    Convert dict into XML string

    :param json_dict: dict 格式的資料 / data as dict
    :return: XML 字串 / XML string
    """

    def _to_elements_tree(json_dict: dict, root):
        if isinstance(json_dict, str):
            # 如果是字串，直接設為節點文字
            # If string, set as node text
            root.text = json_dict
        elif isinstance(json_dict, dict):
            for key, value in json_dict.items():
                assert isinstance(key, str)
                if key.startswith('#'):
                    # 特殊 key "#text" -> 設定文字
                    # Special key "#text" -> set text
                    assert key == '#text' and isinstance(value, str)
                    root.text = value
                elif key.startswith('@'):
                    # 特殊 key "@attr" -> 設定屬性
                    # Special key "@attr" -> set attribute
                    assert isinstance(value, str)
                    root.set(key[1:], value)
                elif isinstance(value, list):
                    # 如果是 list，為每個元素建立子節點
                    # If list, create sub-element for each item
                    for elements in value:
                        _to_elements_tree(elements, ElementTree.SubElement(root, key))
                else:
                    # 一般情況，建立子節點
                    # Normal case, create sub-element
                    _to_elements_tree(value, ElementTree.SubElement(root, key))
        else:
            raise TypeError('invalid type: ' + str(type(json_dict)))

    # dict 必須只有一個根節點
    # dict must have exactly one root element
    assert isinstance(json_dict, dict) and len(json_dict) == 1
    tag, body = next(iter(json_dict.items()))

    # 建立根節點
    # Create root element
    node = ElementTree.Element(tag)

    # 遞迴處理子節點
    # Recursively process children
    _to_elements_tree(body, node)

    # 轉換成字串並回傳
    # Convert to string and return
    return str(ElementTree.tostring(node), encoding="utf-8")