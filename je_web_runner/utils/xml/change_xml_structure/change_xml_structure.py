from collections import defaultdict
# nosec B405,B408 - Element/SubElement/tostring are XML builders, not parsers; defused libs do not provide builders.
from xml.etree.ElementTree import Element, SubElement, tostring  # noqa: S314,S405


def _collect_children(elements_tree) -> dict:
    """Group children by tag and unwrap single-element tags."""
    grouped = defaultdict(list)
    for child_dict in map(elements_tree_to_dict, list(elements_tree)):
        for key, value in child_dict.items():
            grouped[key].append(value)
    return {
        key: value[0] if len(value) == 1 else value
        for key, value in grouped.items()
    }


def _attach_text(elements_dict: dict, elements_tree) -> None:
    """Attach element text content into the dict, with @-attribute and #text rules."""
    if not elements_tree.text:
        return
    text = elements_tree.text.strip()
    has_children = bool(list(elements_tree))
    if has_children or elements_tree.attrib:
        if text:
            elements_dict[elements_tree.tag]['#text'] = text
    else:
        elements_dict[elements_tree.tag] = text


def elements_tree_to_dict(elements_tree) -> dict:
    """
    將 XML ElementTree 轉換成 dict
    Convert XML ElementTree into a Python dict

    :param elements_tree: XML ElementTree 的根節點 / root element of XML tree
    :return: dict 格式的資料 / data as dict
    """
    children = list(elements_tree)
    if children:
        elements_dict: dict = {elements_tree.tag: _collect_children(elements_tree)}
    else:
        elements_dict = {elements_tree.tag: {} if elements_tree.attrib else None}

    if elements_tree.attrib:
        elements_dict[elements_tree.tag].update(
            ('@' + key, value) for key, value in elements_tree.attrib.items()
        )

    _attach_text(elements_dict, elements_tree)
    return elements_dict


def _set_text(root, value) -> None:
    if not isinstance(value, str):
        raise TypeError("#text value must be str")
    root.text = value


def _set_attribute(root, key: str, value) -> None:
    if not isinstance(value, str):
        raise TypeError(f"attribute value for {key!r} must be str")
    root.set(key[1:], value)


def _build_dict_node(json_dict: dict, root) -> None:
    for key, value in json_dict.items():
        if not isinstance(key, str):
            raise TypeError("XML element keys must be str")
        if key == '#text':
            _set_text(root, value)
        elif key.startswith('@'):
            _set_attribute(root, key, value)
        elif isinstance(value, list):
            for item in value:
                _to_elements_tree(item, SubElement(root, key))
        else:
            _to_elements_tree(value, SubElement(root, key))


def _to_elements_tree(json_dict, root) -> None:
    if isinstance(json_dict, str):
        root.text = json_dict
    elif isinstance(json_dict, dict):
        _build_dict_node(json_dict, root)
    else:
        raise TypeError('invalid type: ' + str(type(json_dict)))


def dict_to_elements_tree(json_dict: dict) -> str:
    """
    將 dict 轉換成 XML 字串
    Convert dict into XML string

    :param json_dict: dict 格式的資料 / data as dict
    :return: XML 字串 / XML string
    """
    if not isinstance(json_dict, dict):
        raise TypeError("json_dict must be a dict")
    if len(json_dict) != 1:
        raise ValueError("json_dict must have exactly one root element")

    tag, body = next(iter(json_dict.items()))
    node = Element(tag)
    _to_elements_tree(body, node)
    return str(tostring(node), encoding="utf-8")
