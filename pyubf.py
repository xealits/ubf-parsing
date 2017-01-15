"""
UBF parsed in Python 3

План:
    * написать функции-парсеры каждого элемента УБФ,
      которые вытягивают из стрима свой элемент до "неожидаемого" байта,
      возвращают полученный элемент (классы следуют)
      и остаток стрима
    * "recognition stack" -- расширение dict из зарезерв. байтов -> парсеры
    * парсеры композитных элементов (tuple, list, "1-ый элемент или УБФ-месседж/документ")
      используют стек для распознавания составных элементов
    * объекты, соотв-щие УБФ элементам
      -- расширения питоновских объектов на семантический тег

Обновление плана из-за поточности стрима:
    * сделать таки объект "recognition stack"
      который по-байтово читает стрим
      и наполняет "текущий элемент" байтами
      либо складывает готовый "текущий элемент" в свой стэк,
      в зависимости от нового "текущего элемента" рекогнишн может достать элемент из стэка
      и добавить к нему семантик тэг,
      или начать парсить бинарник с длиной инт,
      или аппендить элемент в список
    * таких объектов должно быть 2 класса
      --- внутри-тапловый стэк и стэк "УБФ документа/месседжа",
      т.е. тот в котором может быть только 1 элемент до знака $
      (нужны будут дополнительные проверки для этого)
"""



# UBF elements

class UBF_Element:
    semantic_tag = None


'''
TODO:
    adding it to __init__ as mixing with built-ins int, str etc
    makes troubles
    --- need to resolve them sometime
    now the simplest solution

    def __init__(self, *args, semantic_tag=None):
        print("UBFing")
        self.semantic_tag = semantic_tag
'''


class UBF_Int(int, UBF_Element):
    pass

class UBF_Str(str, UBF_Element):
    pass

class UBF_Const(str, UBF_Element):
    # TODO: add limit on string length?
    pass

class UBF_Bin(bytes, UBF_Element):
    pass


class UBF_Tuple(tuple, UBF_Element):
    pass

class UBF_List(list, UBF_Element):
    pass



# Parsers

all_bytes = set(range(256))
int_b   = set(b"0123456789")
tilde_b = set(b"~")

def ubf_int_parser(byte_stream, current_position):
    x = b''.join(iter(lambda: byte_stream.read(1), all_bytes - int_b))
    return UBF_Int(x), current_position + len(x), byte_stream



