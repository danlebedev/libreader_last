from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from xml.etree import ElementTree
from xml.etree.ElementTree import Element
import os
import base64


LIBRARY_ROOT = '/home/user/Desktop/library_last'


def index(request):
    structure  = load_structure(LIBRARY_ROOT)
    context = {"data": structure}
    return render(request, 'reader_app/index.html', context)


def book(request, book_dir):
    structure  = load_structure(os.path.join(LIBRARY_ROOT, str(book_dir)))
    context = {"data": structure, "book_dir": book_dir}
    return render(request, 'reader_app/book.html', context)


def chapter(request, book_dir, chapter_dir):
    chapter_root = os.path.join(LIBRARY_ROOT, str(book_dir), str(chapter_dir))
    with open(os.path.join(chapter_root, 'info.xml')) as fp:
        info_xml = ElementTree.parse(fp)
    with open(os.path.join(chapter_root, 'document.xml')) as fp:
        document_xml = ElementTree.parse(fp)
    body = document_xml.getroot()
    images = document_xml.findall('.//image')
    codes = document_xml.findall('.//code')
    consoles = document_xml.findall('.//console')

    def clean(element: Element):
        if element.text and element.text.strip() == '':
            element.text = None
        if element.tail and element.tail.strip() == '':
            element.tail = None
        
        for child in element:
            clean(child)

    clean(body)

    def image_processing(images: list[Element], images_root):
        for image in images:
            try:
                with open(os.path.join(images_root, image.get('src')), 'rb') as fp:
                    img_data = fp.read()
                encoded_image = base64.b64encode(img_data).decode('UTF-8')
                image.attrib['src'] = f"data:image/png;base64,{encoded_image}"
            except:
                pass
    def code_processing(codes: list[Element], codes_root):
        for code in codes:
            code_root = os.path.join(codes_root, code.get('src', ''))
            o_image = code.find('.//image')
            o_console = code.find('.//console')
            if o_image is not None:
                images.remove(o_image)
                image_processing([o_image], os.path.join(os.path.split(code_root)[0], 'image'))
            if o_console is not None:
                consoles.remove(o_console)
                console_processing([o_console], os.path.join(os.path.split(code_root)[0], 'console'))
            try:
                with open(os.path.join(codes_root, code.get('src', '')), encoding='utf-8') as fp:
                    text = fp.read()
                    code.text = text
                    #code.insert(0, text)
            except Exception as e:
                code.text = f"{e}\n"
    def console_processing(consoles: list[Element], consoles_root):
        for console in consoles:
            try:
                with open(os.path.join(consoles_root, console.get('src', '')), encoding='utf-8') as fp:
                    text = fp.read()
                    console.text = text
                    #console.insert(0, text)
            except Exception as e:
                console.text = f"{e}\n"

    code_processing(codes, os.path.join(chapter_root, 'code'))
    image_processing(images, os.path.join(chapter_root, 'image'))
    console_processing(consoles, os.path.join(chapter_root, 'console'))

    context = {
        'header': ElementTree.tostring(info_xml.getroot().find('header'), encoding='unicode'),
        'title': ''.join(info_xml.getroot().find('header').find('p').itertext()),
        'body': ElementTree.tostring(document_xml.getroot(), encoding='unicode'),
    }
    return render(request, 'reader_app/chapter.html', context)


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


@require_GET
def search_api(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})

    results = search_in_library(query)
    return JsonResponse({'results': results})


def search_in_library(query: str):
    results = []
    for book in os.scandir(LIBRARY_ROOT):
        if book.is_file() or not book.name.isnumeric():
            continue

        for chapter in os.scandir(book.path):
            if chapter.is_dir() and chapter.name.isnumeric():
                with open(os.path.join(chapter.path, 'info.xml')) as fp:
                    header = fp.read()
                with open(os.path.join(chapter.path, 'document.xml')) as fp:
                    body = fp.read()
                for item in query.split():
                    if item.lower() not in header.lower() and item.lower() not in body.lower():
                        break
                else:
                    with open(os.path.join(book.path, '_config', 'structure.xml'), encoding='utf-8') as fp:
                        book_struct = fp.read()
                    results.append({
                        'title': ''.join(
                            [
                            ElementTree.fromstring(book_struct).text,
                            '/',
                            *[elem for elem in ElementTree.fromstring(header).itertext()]]),
                        'book_id': os.path.split(book)[-1],
                        'chapter_id': os.path.split(chapter)[-1],
                    })
    return results
