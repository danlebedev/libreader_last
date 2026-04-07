from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from xml.etree import ElementTree
from xml.etree.ElementTree import Element
import os
import base64
import re


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
    """AJAX endpoint для поиска по библиотеке"""
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})
    
    results = search_in_library(query)
    return JsonResponse({'results': results, 'query': query})


def search_in_library(query):
    """
    Поиск по всем файлам в библиотеке
    Возвращает список словарей с информацией о найденных файлах
    """
    results = []
    query_lower = query.lower()
    
    # Обходим все папки книг
    for book_dir in os.listdir(LIBRARY_ROOT):
        book_path = os.path.join(LIBRARY_ROOT, book_dir)
        if not os.path.isdir(book_path) or book_dir == '_config':
            continue
            
        # Обходим все папки глав
        for chapter_dir in os.listdir(book_path):
            chapter_path = os.path.join(book_path, chapter_dir)
            if not os.path.isdir(chapter_path):
                continue
            
            # Получаем заголовок главы ДО поиска
            title = get_chapter_title(book_path, chapter_dir)
            
            # Ищем в document.xml
            doc_path = os.path.join(chapter_path, 'document.xml')
            if os.path.exists(doc_path):
                try:
                    with open(doc_path, 'r', encoding='utf-8') as f:
                        content = f.read().lower()
                        if query_lower in content:
                            # Находим сниппет с контекстом
                            snippet = get_snippet(content, query_lower)
                            results.append({
                                'title': title,  # Используем полученный заголовок
                                'book_dir': book_dir,
                                'chapter_dir': chapter_dir,
                                'type': 'document',
                                'snippet': snippet,
                            })
                            continue  # чтобы не добавлять одну главу несколько раз
                except Exception as e:
                    print(f"Ошибка чтения {doc_path}: {e}")
                    pass
            
            # Ищем в файлах кода
            code_path = os.path.join(chapter_path, 'code')
            if os.path.exists(code_path):
                for code_file in os.listdir(code_path):
                    if code_file.endswith(('.txt', '.py', '.c', '.cpp', '.java', '.html', '.css', '.js')):
                        try:
                            with open(os.path.join(code_path, code_file), 'r', encoding='utf-8') as f:
                                content = f.read().lower()
                                if query_lower in content:
                                    snippet = get_snippet(content, query_lower)
                                    results.append({
                                        'title': title,  # Используем полученный заголовок
                                        'book_dir': book_dir,
                                        'chapter_dir': chapter_dir,
                                        'type': 'code',
                                        'file': code_file,
                                        'snippet': snippet,
                                    })
                                    break
                        except Exception as e:
                            print(f"Ошибка чтения кода {code_file}: {e}")
                            pass
            
            # Ищем в файлах консоли
            console_path = os.path.join(chapter_path, 'console')
            if os.path.exists(console_path):
                for console_file in os.listdir(console_path):
                    if console_file.endswith('.txt'):
                        try:
                            with open(os.path.join(console_path, console_file), 'r', encoding='utf-8') as f:
                                content = f.read().lower()
                                if query_lower in content:
                                    snippet = get_snippet(content, query_lower)
                                    results.append({
                                        'title': title,  # Используем полученный заголовок
                                        'book_dir': book_dir,
                                        'chapter_dir': chapter_dir,
                                        'type': 'console',
                                        'file': console_file,
                                        'snippet': snippet,
                                    })
                                    break
                        except Exception as e:
                            print(f"Ошибка чтения консоли {console_file}: {e}")
                            pass
    
    return results[:50]  # ограничиваем 50 результатами


def get_snippet(content, query, context_chars=100):
    """Возвращает фрагмент текста с искомым словом в контексте"""
    pos = content.find(query)
    if pos == -1:
        return content[:context_chars] + '...' if len(content) > context_chars else content
    
    start = max(0, pos - context_chars)
    end = min(len(content), pos + len(query) + context_chars)
    
    snippet = content[start:end]
    
    # Добавляем многоточие, если вырезали начало или конец
    if start > 0:
        snippet = '...' + snippet
    if end < len(content):
        snippet = snippet + '...'
    
    # Очищаем от XML тегов для красивого отображения
    snippet = re.sub(r'<[^>]+>', ' ', snippet)
    snippet = ' '.join(snippet.split())  # убираем лишние пробелы
    
    return snippet


def get_chapter_title(book_path, chapter_dir):
    """Получает заголовок главы из info.xml"""
    info_path = os.path.join(book_path, chapter_dir, 'info.xml')
    try:
        with open(info_path, 'r', encoding='utf-8') as fp:
            info_xml = ElementTree.parse(fp)
            root = info_xml.getroot()
            
            # Пробуем найти header разными способами
            header = root.find('header')
            
            if header is not None:
                # Получаем текст, включая текст из вложенных тегов
                if header.text and header.text.strip():
                    title = header.text.strip()
                    print(f"Найден заголовок (text): {title}")  # Отладка
                    return title
                else:
                    # Если текст внутри вложенных тегов
                    title = ''.join(header.itertext()).strip()
                    if title:
                        print(f"Найден заголовок (itertext): {title}")  # Отладка
                        return title
            
            # Если header не найден, пробуем найти title или name
            title_elem = root.find('title') or root.find('name')
            if title_elem is not None:
                title = ''.join(title_elem.itertext()).strip()
                if title:
                    print(f"Найден заголовок (title/name): {title}")  # Отладка
                    return title
            
            print(f"Заголовок не найден для {chapter_dir}, использую имя папки")  # Отладка
            return f"Глава {chapter_dir}"
            
    except Exception as e:
        print(f"Ошибка чтения {info_path}: {e}")
        return f"Глава {chapter_dir}"
