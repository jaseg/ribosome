#!/usr/bin/env python

from __future__ import print_function, division

#
# Copyright (c) 2015 Ali Zaidi  All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom
# the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#

import os
import re
import sys
import ast, _ast
import inspect
import unicodedata

line = lambda level=1: inspect.stack()[level][2]
templ = lambda s, level=1: s.format(**inspect.stack()[level][0].f_locals)
dnacontext = lambda: inspect.currentframe().f_back.f_back.f_locals
contextvar = lambda s: dnacontext[s]
tabcollate = lambda s, ts: re.sub('^( {'+str(ts)+'})*', lambda m: '\t'*(m.end()//ts), s)


class Document:
    """ Text document that supports multi-line expansion in append functions.

    All public manipulation functions accept a list of line chunks that are stuck to each other like this:
      [-----] [-chunk 2-] [---chunk 3----] [-chunk-]
      |chunk| [---------]                  |   4   |
      |  1  |                              [-------]
      [-----]
    Each chunk may by itself contain multiple lines.
    """

    def __init__(self, out=sys.stdout, s='', tabsize=0):
        self.text = []
        self.cur = s.splitlines()
        self.out = out
        self.tabsize = tabsize

    def _add_elem(self, *elines):
        w = max(len(l) for l in self.cur or [''])
        d = len(elines)-len(self.cur) # to pad cur and line to equal lengths
        self.cur = [c.ljust(w)+l for c,l in zip(self.cur+['']*max(d, 0), elines+('',)*max(-d, 0))]

    def add(self, *line):
        """ Weld the supplied block to the right of the current block """
        for elem in line:
            self._add_elem(*(elem.splitlines() or ['']))

    def dot(self, *line):
        """ Weld the supplied block to the bottom of the current block """
        self.text += self.cur
        self.cur = []
        self.add(*line)

    def align(self, *line):
        """ Like dot, but left-align content with previous line """
        indent = ' '*max(re.match('[\s]*', l).end() for l in self.cur)
        self.dot(*( indent+l for l in line ))

    # Output control
    def write(self):
        self.dot()
        self.out.write('\n'.join(tabcollate(line, self.tabsize) if self.tabsize else line for line in self.text))

    def close(self):
        self.write()
        self.out.write('\n')
        self.out.close()


_separate_state = {}
def separate(sep, sid, add):
    global _separate_state
    if not _separate_state.get(sid):
        _separate_state[sid] = True
    else:
        add(sep)

            
def include(file_or_name, _globals=None):
    """ Include another DNA document

    This document will have access to any local variables and functions from the including document. The including
    document, in turn, will **NOT** have access to anything locally declared in the included document.
    """
    includefile = open(file_or_name, 'r') if isinstance(file_or_name, str) else file_or_name

    caller_f = inspect.currentframe().f_back
    _globals = _globals or caller_f.f_globals.copy()
    filename, warnctx = _globals['_filename'], _globals['_warnctx']
    lineno = caller_f.f_lineno
    def newwarnctx():
        warnctx(s)
        print('At {}:{}'.format(filename, lineno), file=sys.stderr)

    _globals.update({ '_filename': includefile.name, '_warnctx': newwarnctx })

    with includefile as f:
        tree = parse_lines(includefile.name, includefile.readlines(), newwarnctx)
        code = compile(tree, includefile.name, 'exec')
        exec(code, _globals)

def parse_lines(filename, lines, warnctx):
    def warn(s):
        warnctx()
        print('From {}:{}'.format(__file__, line(2)), file=sys.stderr)
        print(templ(s, 2), file=sys.stderr)
        print('> '+rawline, file=sys.stderr)

    code = []
    for lineno,rawline in enumerate(lines):
        indent,     dot,     shortcmd,    line,    rspace,     dollar = re.match(
        r'^([\s]*)'+r'(\.?)'+r'(/[+=!])?'+r'(.*?)'+r'([\s]*?)'+r'(\$?)\n?$', rawline).groups()

        if rspace and not dollar:
            warn('Trailing space in line not dollar-terminated')

        if '\t' in rawline:
            warn("Line contains tabs. For consistent results, consider using spaces.")

        if not dot:
            code.append(rawline.rstrip('\n'))
            continue

        def repl(s):
            m = re.search(r'([@&])0?([1-9]?)\{', s)
            if not m:
                return repr(s)
            start,end, = m.span()
            op, ncount = m.groups()
            lvl = 1
            for b in re.finditer('[{}]', s[end:]):
                lvl += 1 if b.group(0) == '{' else -1
                if lvl == 0:
                    if ncount:
                        if ncount != '1':
                            s = s[:m.end()-2] + str(int(ncount)-1) + s[m.end()-1:]
                        else:
                            s = s[:m.end()-2] + s[m.end()-1:]
                        return repr(s[:end+b.end()]) + repl(s[end+b.end():])
                    else:
                        return ', '.join([ repr(s[:start]),
                            ("str({}).strip()" if op == '@' else "str({})").format(s[end:end+b.start()])
                            , repl(s[end+b.end():]) ])

        if not shortcmd:
            cmd, args = 'dot', repl(line)
        elif shortcmd == '/+': # Append the line to the previous line.
            cmd, args = 'add', repl(line)
        elif shortcmd == '/=': # /= Align the line with the previous line.
            cmd, args = 'align', repl(line)
        else:
            m = re.match(r'(^[0-9A-Za-z_]+)\((.*)\)$', line)
            if not m:
                warn('Invalid command syntax. Expected: /!command(arg, etc)')
                code.append('# Invalid command syntax: {}'.format(rawline))
                continue
            cmd, args = m.groups()
        code.append(templ('{indent}{cmd}({args})'))

    if DEBUG:
        print('GENERATED:')
        print('\n'.join(code))
        print('---')
    tree = ast.parse('\n'.join(code), filename)

    # Fix up generated AST for "separate" commands
    # from _ast import * does not work in python2
    done = []
    for node in ast.walk(tree):
        for val in node.__dict__.values():
            if type(val) is list:
                indices = [i for i,e in enumerate(val) if
                        type(e) is _ast.Expr and
                        type(e.value) is _ast.Call and
                        type(e.value.func) is _ast.Name and
                        e.value.func.id == 'separate']
                for idx in reversed(indices):
                    sepcall, loop = val[idx], val[idx+1]
                    if sepcall in done:
                        continue #FIXME dirty hack
                    if type(loop) not in (_ast.For, _ast.While, _ast.FunctionDef):
                        warn('"separate" command must be followed by loop or function definition.')
                        continue
                    sepcall.value.args.append(ast.Str('{}:{}'.format(filename, idx)))
                    sepcall.value.args.append(ast.Name('add', ast.Load()))
                    ast.fix_missing_locations(sepcall)
                    loop.body = [sepcall] + loop.body
                    done.append(sepcall)
                    del val[idx]
    return tree

# Escape sequences
at    = '@'
amp   = '&'
slash = '/'

def runfile(f):
    _doc = Document()

    def redirect(f):
        _doc.close()
        _doc = Document(f)

    def tabsize(ts):
        _doc.tabsize = ts

    _globals = globals().copy()
    _globals.update({
        '_filename': '<ribosome>',
        '_warnctx' : lambda: None,
        '_doc'     : _doc,
        'redirect' : redirect,
        'tabsize'  : tabsize,
        'add'      : lambda *line: _doc.add(*line),
        'dot'      : lambda *line: _doc.dot(*line),
        'align'    : lambda *line: _doc.align(*line),
        'close'    : lambda: _doc.close(),
        'stdout'   : lambda: redirect(sys.stdout),
        'stderr'   : lambda: redirect(sys.stderr),
        'output'   : lambda filename: redirect(open(filename, "w")),
        'append'   : lambda filename: redirect(open(filename, "a")) })


    include(f, _globals)
    _doc.close()

DEBUG = False
if __name__ == '__main__':
    # Set up the arguments parser.
    import argparse
    parser = argparse.ArgumentParser(prog="ribosome code generator, version 1.16")
    parser.add_argument('dna', type=argparse.FileType('r'), default=sys.stdin)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    DEBUG = args.debug
    runfile(args.dna)

