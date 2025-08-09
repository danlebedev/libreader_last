from django.shortcuts import render
from xml.etree import ElementTree
from xml.etree.ElementTree import Element
import os


LIBRARY_ROOT = '/home/user/Desktop/library_last'


def index(request):
    structure  = load_structure(LIBRARY_ROOT)
    context = {"data": structure}
    return render(request, 'reader_app/index.html', context)


def book(request, book_dir):
    structure  = load_structure(os.path.join(LIBRARY_ROOT, str(book_dir)))
    context = {"data": structure, "book_dir": book_dir}
    return render(request, 'reader_app/book.html', context)


def xml_to_json(element: Element):
    result = {'name': element.text.strip(), 'list': []}
    for node in element:
        if len(node):
            result['list'].append(xml_to_json(node))
        else:
            result['list'].append({'name': node.text.strip(), **node.attrib})
    return result


def load_structure(path):
    with open(os.path.join(path, '_config/structure.xml')) as fp:
        return xml_to_json(ElementTree.parse(fp).getroot())

