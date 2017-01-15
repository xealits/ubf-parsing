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



# UBF reserved characters

'''
all_bytes = set(bytes(range(256)))
int_b   = set(b"0123456789")
minus_b = set(b"-")
tilde_b = set(b"~")
stringquote = set(b'"')
constquote  = set(b"'")
semanticquote = set(b"`")
whitespace = set(b" \t\n\r,")
comment_b  = set(b"%")
tuple_b = set(b"{}")
list_b  = set(b"#")
append_b = set(b"&")
end_b = set(b"$")
'''

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

# awesome state machinning without tail recursion and only-1-statement lambda
# so much useless helper_func names..
# that's why "metaprogramming" exists

def raise_typeerror(b):
    raise TypeError("Expected a control byte, not %x" % b)

def run_coms(func_list, b):
    for f in func_list:
        f(b)

def dummy(*args):
    pass

act_all_notexp = {b: lambda _, b: raise_typeerror(b) for b in all_bytes}

none_act = act_all_notexp
none_act.update({b: lambda rc, b:
    run_coms([lambda _: rc.state("Int"),
              lambda b: rc.pool(bytes([b]))], # yep, that's how it's done, Python3, no byte for bytes
             b)
    for b in int_b + minus_b}) # Enter Int recognition
none_act.update({tilde_b[0]: # Enter-Load-and-Finish Bin recognition
    lambda rc, b: 
      run_coms([lambda _: rc.load_bin(rc.pop_int()), # load Int (from the stack) bytes from stream
                # to properly finish the Bin recognition
                # the next byte has to be checked if it is ~
                lambda _: rc.check_final_tilde() ],
               b)})
none_act.update({semanticquote[0]: lambda rc, b:
      run_coms([lambda _: rc.state("SemanticTag"),
                lambda _: rc.pool(bytes())],
               b)})
none_act.update({stringquote[0]: lambda rc, b:
      run_coms([lambda _: rc.state("Str"),
                lambda _: rc.pool(bytes())],
               b)})
none_act.update({constquote[0]: lambda rc, b:
      run_coms([lambda _: rc.state("Const"),
                lambda _: rc.pool(bytes())],
               b)})
none_act.update({b: dummy
    for b in whitespace})

#int_act = act_all_notexp
int_act = {b: lambda rc, b: rc.pool_up(b) for b in int_b}
int_act.update({b: lambda rc, b:
    run_coms([lambda _: rc.recognized_stack.append(UBF_Int(rc._pool)), # Finish Int recognition
              lambda _: rc.pool(None),       # clear pool
              lambda _: rc.state(None),      # move to None state
              lambda b: none_act[b](rc, b)], # decision in None state
            b)
    for b in bytes(set(all_bytes) - set(int_b))})

# for now let's do these strings simply 
# -- without the escaping
# and semantic_tag is just bytes
sem_act = {b: lambda rc, b: rc.pool_up(b) for b in set(all_bytes) - set(semanticquote)}
sem_act.update({semanticquote[0]: lambda rc, b:
    run_coms([lambda _: rc.update_sematic_tag(rc._pool), # update semantic tag (bytes) in the last element of the rc
              lambda _: rc.state(None),
              lambda _: rc.pool(None)],
             b)})

str_act = {b: lambda rc, b: rc.pool_up(b) for b in set(all_bytes) - set(stringquote)}
str_act.update({stringquote[0]: lambda rc, b:
    run_coms([lambda _: rc.recognized_stack.append(UBF_Str(rc._pool)),
              lambda _: rc.state(None),
              lambda _: rc.pool(None)],
             b)})

const_act = {b: lambda rc, b: rc.pool_up(b) for b in set(all_bytes) - set(constquote)}
const_act.update({constquote[0]: lambda rc, b:
    run_coms([lambda _: rc.recognized_stack.append(UBF_Const(rc._pool)),
              lambda _: rc.state(None),
              lambda _: rc.pool(None)],
             b)})

default_stack_actions = {
        None: none_act,
        "Int": int_act,
        # "Bin": bin_act, # Bin recognition is done by the recognition stack object method in 1 go
        "SemanticTag": sem_act,
        "Str": str_act,
        "Const": const_act
        }


# Recognition stacks

class RecognitionStack:
    """
    TODO: initialize with registers

    Keeps a stack (list) of recognized UBF elements
    and a pool (bytes) for the current element.
    Reeds bytes stream, updating the current element pool or the stack.

    This class implements no-current-element recognition
    """

    """
    Needed rc methods:
        update_semantic_tag(bytes)
        check_final_tilde()
        load_bin(UBF_Int)
        pop_int() --- check UBF_Int
    """

    def __init__(self, stream = None, stream_bytes_read = 0):
        self.stream = stream
        self.stream_bytes_read = stream_bytes_read
        self.recognized_stack = []
        self._state = None # no element recognition was started
        self._pool  = None # no current elements being recognized
        self.actions = default_stack_actions
        #self.current_pool = None
        #self.current_recognition = (None, None)
        # will be (type-of-element, its'-pool)
        # the pool is bytes for some, or list for UBF tuple
        # UBF list is populated by & with appending to previous element in the stack

        # OR this will be done with classes

    def recognize(self, stream = None, stream_bytes_read = 0):
        if stream:
            self.stream = stream
            self.stream_bytes_read = 0

        if stream_bytes_read:
            self.stream_bytes_read = stream_bytes_read

        # without tail recursion describing states sucks
        while True:
            b = self.stream.read(1)
            if not b:
                # in case we don't block on empty stream
                return UBF_Tuple(self.recognized_stack), self.stream_bytes_read
            else:
                b = b[0]
            self.stream_bytes_read += 1

            #print(self._pool)

            if b == end_b[0]:
                assert self._state == None
                out = UBF_Tuple(self.recognized_stack), self.stream_bytes_read
                self.recognized_stack = []
                self.stream_bytes_read = 0
                return out

            self.actions[self._state][b](self, b)
            # state can be:
            #    None
            #    Int
            #    Str
            #    Bin
            #    Const
            #    SemanticTag
            #    Tuple (or separately)
            #    --- all change/update behaviour of None

    def state(self, new_state):
        self._state = new_state

    def pool(self, init_pool):
        self._pool = init_pool # bytes([init_pool])

    def pool_up(self, b):
        self._pool += bytes([b]) # I wonder how it will work with tuples

    def update_sematic_tag(self, new_sem_tag):
        assert type(new_sem_tag) == bytes
        self.recognized_stack[-1].semantic_tag = new_sem_tag

    def check_final_tilde(self):
        assert self._state is None
        b = self.stream.read(1)[0]
        self.stream_bytes_read += 1

        if b != tilde_b:
            self.actions[self._state][b](self, b)

    def load_bin(self, length):
        self.recognized_stack.append(UBF_Bin(self.stream.read(length)))
        self.stream_bytes_read += length

    def pop_int(self):
        # --- check UBF_Int
        stack_head = self.recognized_stack.pop()
        assert type(stack_head) == UBF_Int
        return stack_head

