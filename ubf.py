# Copyright (c) 2000-2004, 2007 Tony Garnock-Jones <tonyg@kcbbs.gen.nz>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
from __future__ import nested_scopes

import sys
import string
import types

__author__ = 'Tony Garnock-Jones'
__email__ = 'tonyg@kcbbs.gen.nz'

NumTypes = (types.IntType, types.LongType)

class Tag:
    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __cmp__(self, other):
        if isinstance(other, Tag):
            v = cmp(self.key, other.key)
            if v: return v
            return cmp(self.value, other.value)
        else:
            return -1

    def __hash__(self):
        return hash(self.key) ^ hash(self.value)

    def __repr__(self):
        return 'ubf.Tag('+repr(self.key)+','+repr(self.value)+')'

    def __str__(self):
        return repr(self)

class Symbol:
    def __init__(self, name):
        self.name = name

    def __cmp__(self, other):
        if isinstance(other, Symbol):
            return cmp(self.name, other.name)
        else:
            return -1

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return 'ubf.Symbol('+repr(self.name)+')'

    def __str__(self):
        return repr(self)

class Binary:
    def __init__(self, content):
        self.content = content

    def __cmp__(self, other):
        if isinstance(other, Binary):
            return cmp(self.content, other.content)
        else:
            return -1

    def __hash__(self):
        return hash(self.content)

    def __repr__(self):
        return 'ubf.Binary('+repr(self.content)+')'

    def __str__(self):
        return 'ubf.Binary(length = '+str(len(self.content))+')'

ubf_a_reserved_chars = '%"\'`~#&$>-0123456789{}, \n\r\t'

def digit_to_number(x): return ord(x) - ord('0')

class FormatError(Exception): pass
class EndOfStream(FormatError): pass

class Decoder:
    def __init__(self, coll):
        self._iter = iter(coll)
        self.dispatch = None
        self.stack = []
        self.result = None
        self.defaultDispatch = {'%': self._handleComment,
                                '"': self._handleString,
                                "'": self._handleSymbol,
                                '`': self._handleSemanticTag,
                                '~': self._handleBinary,
                                '#': self._handleNull,
                                '&': self._handleCons,
                                '$': self._handleEom,
                                '>': self._handleBind,
                                '-': self._collectInt,
                                '0': self._collectInt,
                                '1': self._collectInt,
                                '2': self._collectInt,
                                '3': self._collectInt,
                                '4': self._collectInt,
                                '5': self._collectInt,
                                '6': self._collectInt,
                                '7': self._collectInt,
                                '8': self._collectInt,
                                '9': self._collectInt,
                                '{': self._handleOpenStruct,
                                '}': self._handleCloseStruct,
                                ' ': self._ignore,
                                '\n': self._ignore,
                                '\r': self._ignore,
                                '\t': self._ignore,
                                ',': self._ignore }

    def decode(self):
        self.dispatch = self.defaultDispatch.copy()
        self.stack = []
        self.result = None

        ch = None
        while self.result is None:
            if ch is None:
                ch = self._chargen()

            if self.dispatch.has_key(ch):
                ch = self.dispatch[ch](ch)
            else:
                raise FormatError('Unhandled UBF-A character', ch)

        return self.result

    def __iter__(self):
        return self

    def next(self):
        try:
            return self.decode()
        except EndOfStream:
            raise StopIteration

    def _push(self, x):
        self.stack.append(x)

    def _pop(self):
        return self.stack.pop()

    def _peek(self):
        return self.stack[-1]

    def _empty(self):
        return (len(self.stack) == 0)

    def _chargen(self):
        try:
            return self._iter.next()
        except StopIteration:
            raise EndOfStream()

    def _collect_quoted(self, stopchar):
        acc = []

        while 1:
            char = self._chargen()
            if char == '\\':
                ch2 = self._chargen()
                if ch2 in ('\\', stopchar):
                    acc.append(ch2)
                else:
                    raise FormatError('Unsupported quoted character', ch2, stopchar)
            elif char == stopchar:
                return string.join(acc, '')
            else:
                acc.append(char)

    def _handleComment(self, char):
        self._collect_quoted(char)
        return None

    def _handleString(self, char):
        self._push(self._collect_quoted(char))
        return None
    
    def _handleSymbol(self, char):
        self._push(Symbol(self._collect_quoted(char)))
        return None
    
    def _handleSemanticTag(self, char):
        tagname = self._collect_quoted(char)
        if self._empty(): raise FormatError('Semantic tag must follow item', tagname)
        self._push(Tag(tagname, self._pop()))
        return None

    def _handleBinary(self, firstTilde):
        if self._empty() or type(self._peek()) not in NumTypes:
            raise FormatError('Binary data must be preceded by length')
        binlen = self._pop()
        acc = []
        i = 0
        while i < binlen:
            acc.append(self._chargen())
            i = i + 1
        if self._chargen() != '~':
            raise FormatError('Binary data must be followed by tilde')
        self._push(Binary(string.join(acc, '')))
        return None

    def _handleNull(self, ch):
        self._push([])
        return None

    def _handleCons(self, ch):
        a = self._pop()
        self._peek().insert(0, a)
        return None

    def _handleEom(self, ch):
        if self._empty(): raise FormatError('Empty stack at end of message')
        self.result = self._pop()
        if not self._empty(): raise FormatError('Rubbish remains on stack at UBF EOM token')
        return None

    def _handleBind(self, dummy):
        ch = self._chargen()
        if ch in ubf_a_reserved_chars:
            raise FormatError('Attempt to bind to reserved character', ch)
        val = self._pop()
        def handler(dummy2):
            self._push(val)
            return None
        self.dispatch[ch] = handler
        return None

    def _collectInt(self, ch):
        if ch == '-':
            sign = -1
            acc = 0
        else:
            sign = 1
            acc = digit_to_number(ch)

        while 1:
            ch = self._chargen()
            if ch >= '0' and ch <= '9':
                acc = acc * 10 + digit_to_number(ch)
            else:
                self._push(sign * acc)
                return ch

    def _handleOpenStruct(self, ch):
        self._push({}) # magic marker
        return None

    def _handleCloseStruct(self, ch):
        acc = []
        while 1:
            v = self._pop()
            if v == {}:
                acc.reverse()
                self._push(tuple(acc))
                break
            else:
                acc.append(v)
        return None

    def _ignore(self, ch):
        return None

    def __repr__(self):
        return '<ubf.Decoder ' + repr(self.stack)+ '>'

    def __str__(self):
        return repr(self)

class Encoder:
    regpref = list("abcdefghijklmnopqrstuvwxyz" + \
                   "ABCDEFGHIJKLMNOPQRSTUVWXYZ" + \
                   ".,:;[]\\|+=_()*^@!")
    for i in range(255, -1, -1):
        ch = chr(i)
        if ch in regpref or ch in ubf_a_reserved_chars:
            pass
        else:
            regpref.append(ch)
    
    def __init__(self):
        pass

    def build_table(self, object):
        table = {}
        def walk(x):
            if type(x) in (types.TupleType, types.ListType):
                for elt in x: walk(elt)
            elif isinstance(x, Tag):
                walk(x.value)
            else:
                if table.has_key(x):
                    table[x] = table[x] + 1
                else:
                    table[x] = 1
        walk(object)
        freqtab = [(v,k) for (k,v) in table.iteritems()]
        freqtab.sort()
        regtab = {}
        reglist = self.regpref[:]
        for (count, x) in freqtab:
            if count > 1:
                if type(x) not in NumTypes or x < 0 or x > 9:
                    regname = reglist[0]
                    reglist = reglist[1:]
                    regtab[x] = [regname, False]
        return regtab

    def encode(self, object, buildTable = True):
        self.wrote_integer = False
        if buildTable:
            self.table = self.build_table(object)
        else:
            self.table = None
        self._encode(object)
        self.emit('$')
        return self.finish()

    def _quote_string(self, quotechar, str):
        self.emit(quotechar)
        for ch in str:
            if ch in ('\\', quotechar):
                self.emit('\\')
            self.emit(ch)
        self.emit(quotechar)

    def _encode(self, object):
        new_wrote_integer = False
        entry = None

        if type(object) == types.TupleType:
            self.emit('{')
            for x in object:
                self._encode(x)
            self.emit('}')
        elif type(object) == types.ListType:
            self.emit('#')
            seq = object[:]
            seq.reverse()
            for x in seq:
                self._encode(x)
                self.emit('&')
        elif isinstance(object, Tag):
            self._encode(object.value)
            self._quote_string('`', object.key)
        else:
            if self.table and self.table.has_key(object):
                entry = self.table[object]

            if entry and entry[1]:
                self.emit(entry[0])
            elif type(object) in NumTypes:
                if self.wrote_integer and object >= 0:
                    self.emit(' ')
                for ch in str(object):
                    self.emit(ch)
                new_wrote_integer = True
            elif type(object) == types.StringType:
                self._quote_string('"', object)
            elif isinstance(object, Symbol):
                self._quote_string("'", object.name)
            elif isinstance(object, Binary):
                self._encode(len(object.content))
                self.emit('~')
                for ch in object.content:
                    self.emit(ch)
                self.emit('~')
            else:
                raise FormatError('Unsupported term type in ubf.Encoder._encode', object)

        if entry and not entry[1]:
            entry[1] = True
            self.emit('>')
            self.emit(entry[0])
            self.emit(entry[0])

        self.wrote_integer = new_wrote_integer

class StringEncoder(Encoder):
    def __init__(self):
        Encoder.__init__(self)
        self.accumulator = []

    def emit(self, ch):
        self.accumulator.append(ch)

    def finish(self):
        return string.join(self.accumulator, '')
