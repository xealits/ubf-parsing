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



# UBF reserved characters

all_bytes = bytes(range(256))
int_b   = b"0123456789"
minus_b = b"-"
tilde_b = b"~"
stringquote = b'"'
constquote  = b"'"
semanticquote = b"`"
whitespace = b" \t\n\r,"
comment_b  = b"%"
tuple_open_b = b"{"
tuple_end_b  = b"}"
list_b  = b"#"
append_b = b"&"
end_b = b"$"

# awesome state machinning with classes as states!

# Recognition stacks

class RecognitionStack_None:
    """
    Initial state of the recognition stack.
    No elements in the stack, no currently recognized element in self._pool.

    Keeps a stack (list) of recognized UBF elements
    and a pool (bytes) for the current element.
    Reeds bytes stream, updating the current element pool or the stack.
    """

    def __init__(self, stream: "byte_stream" = None, stream_bytes_read: int = 0, in_tuple: bool = False):
        #print("rec stac in_tuple = %s" % in_tuple)
        self.stream = stream
        self.stream_bytes_read = stream_bytes_read
        self.recognized_stack = []
        #self.actions = actions
        #self._state = None # no element recognition was started
        # the state is done with classes
        self._pool  = None # no current elements being recognized
        self.in_tuple = in_tuple
        self.recognition_ended = False
        #self.current_pool = None
        #self.current_recognition = (None, None)
        # will be (type-of-element, its'-pool)
        # the pool is bytes for some, or list for UBF tuple
        # UBF list is populated by & with appending to previous element in the stack

    def recognize(self, stream: "byte_stream" = None, stream_bytes_read: int = 0):
        """recognize(self, stream = None, stream_bytes_read = 0)

        Recognizes a full message from the given stream.
        If None stream is given -- looks at self.stream.

        Message end = b'$' or end of stream (empty self.stream.read(1)).
        Asserts recognized stack to be of length 1 at the end of the message.

        Logs number of bytes read in self.stream_bytes_read.
        """

        if stream:
            self.stream = stream
            self.stream_bytes_read = 0

        if stream_bytes_read:
            self.stream_bytes_read = stream_bytes_read

        while not self.recognition_ended:
            b = self.stream.read(1)
            #print(b)
            if not b:
                # in case we don't block on empty stream
                # --- treat empty stream like $ end of message
                #return UBF_Tuple(self.recognized_stack), self.stream_bytes_read
                break
            self.stream_bytes_read += 1

            self.act(b)

        if self.in_tuple:
            out = UBF_Tuple(self.recognized_stack)
        else:
            # TODO: do this check during recognition
            assert len(self.recognized_stack) == 1
            out = self.recognized_stack[0]

        out = out, self.stream_bytes_read

        # return to initial state
        self.recognized_stack = []
        self.stream_bytes_read = 0
        self.recognition_ended = False

        return out

    def act(self, byte: bytes):
        """act(self, byte: bytes)

        Transition of the RecognitionStack according to the read byte.
        """

        assert type(byte) == bytes

        if byte in int_b + minus_b:
            # enter Int recognition
            self.__class__ = RecognitionStack_Int
            self._pool = byte

        elif byte == tilde_b:
            # enter-load-finish Bin recognition
            length = self.recognized_stack.pop()
            assert type(length) == UBF_Int
            self.recognized_stack.append(UBF_Bin(self.stream.read(length)))
            self.stream_bytes_read += length
            # check for final tilde
            b = self.stream.read(1)
            self.stream_bytes_read += 1
            if b != tilde_b:
                self.act(b)

        elif byte == semanticquote:
            self.__class__ = RecognitionStack_SemanticTag
            self._pool = bytes()
        elif byte == stringquote:
            self.__class__ = RecognitionStack_Str
            self._pool = bytes()
        elif byte == constquote:
            self.__class__ = RecognitionStack_Const
            self._pool = bytes()

        elif byte in whitespace:
            pass

        elif byte == list_b:
            self.recognized_stack.append(UBF_List())
        elif byte == append_b:
            self.recognized_stack[-2].append(self.recognized_stack.pop())

        elif byte == end_b:
            assert not self.in_tuple
            # "Did not expect end of message $ inside tuple, stream %s at %d" % (rc.stream, rc.stream_bytes_read)
            self.recognition_ended = True

        elif byte == tuple_open_b:
            # the line is long indeed
            # I'm making point that the recognition stack is temporary
            tuple_element, stream_bytes_read = RecognitionStack(self.stream, self.stream_bytes_read, in_tuple = True).recognize()
            self.recognized_stack.append(tuple_element)
            self.stream_bytes_read = stream_bytes_read
        elif byte == tuple_end_b:
            assert self.in_tuple
            self.recognition_ended = True

        else:
            # TODO: add registers
            raise TypeError("Expected a control byte, not %s at %d in %s" % (str(byte), self.stream_bytes_read, self.stream))

RecognitionStack = RecognitionStack_None # allias for initial state

class RecognitionStack_Int:
    def act(self, byte: bytes):
        if byte in int_b:
            self._pool += byte
        else:
            # finish the Int recognition
            # store the recognized Int
            # return to None state
            self.recognized_stack.append(UBF_Int(self._pool))
            self._pool = None
            self.__class__ = RecognitionStack_None
            self.act(byte)


class RecognitionStack_SemanticTag:
    def act(self, byte: bytes):
        if byte != semanticquote:
            # TODO: add escaping
            self._pool += byte
        else:
            # finish the SemanticTag recognition
            # update the semantic tag of the last element in the stack
            # return to None state
            self.recognized_stack[-1].semantic_tag = self._pool
            self._pool = None
            self.__class__ = RecognitionStack_None

class RecognitionStack_Str:
    def act(self, byte: bytes):
        if byte != stringquote:
            # TODO: add escaping
            self._pool += byte
        else:
            # finish the Str recognition
            # store Str element
            # return to None state
            self.recognized_stack.append(UBF_Str(self._pool))
            self._pool = None
            self.__class__ = RecognitionStack_None

class RecognitionStack_Const:
    def act(self, byte: bytes):
        if byte != constquote:
            # TODO: add escaping
            # TODO: should I check the length of constants?
            # otherwise they are like str
            self._pool += byte
        else:
            # finish the Const recognition
            # store Const element
            # return to None state
            self.recognized_stack.append(UBF_Const(self._pool))
            self._pool = None
            self.__class__ = RecognitionStack_None


