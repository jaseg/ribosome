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

line = lambda: inspect.currentframe().f_back.f_lineno
templ = lambda s, level=1: s.format(**inspect.stack()[level][0].f_locals)


#################
# Prologue code #
#################

class Block:
    # Block represents a rectangular area of text.

    def __init__(self, s):
        self.text = ['']
        self.width = 0
        if len(s) > 0:
            self.text = s.splitlines()
            self.width = max(map(lambda x: len(x), self.text))

    # Weld the supplied block to the right of this block
    def add_right(self, block):
        for i, l in enumerate(block.text):
            try:
                self.text[i] += ' ' * (self.width - len(self.text[i])) + l
            except:
                self.text.append((' ' * self.width) + l)
        self.width += block.width

    # Weld the supplied block to the bottom of this block
    def add_bottom(self, block):
        self.text += block.text
        self.width = max([self.width, block.width])

    # Trim the whitespace from the block
    def trim(self):
        top = bottom = left = right = -1
        for i, l in enumerate(self.text):
            if not l.strip() == '':
                # line is not empty
                if top == -1: top = i
                bottom = i
                ls = len(l) - len(l.lstrip())
                left = ls if left == -1 else min([left, ls])
                rs = len(l.rstrip())
                right = rs if right == -1 else max([right, rs])
        if bottom == -1:
            # empty block
            self.text = ['']
            self.width = 0
        # Strip off the top and bottom whitespace.
        self.text = self.text[top:bottom+1]
        # Strip off the whitespace on the left and on the right.
        self.text = [l.rstrip()[left:right+1] for l in self.text]
        # Adjust the overall width of the block.
        self.width = max([len(l) for l in self.text])
        
    def write(self, out, tabsize):
        for l in self.text:
            # If required, replace the initial whitespace by tabs.
            if tabsize > 0:
                ws = len(l) - len(l.lstrip())
                l = '\t' * (ws // tabsize) + ' ' * (ws % tabsize) + l.lstrip()
            # Write an individual line to the output file.
            out.write(l+'\n')

    # Returns offset of the last line in block
    def last_offset(self):
        if len(self.text) == 0: return 0
        return len(self.text[-1]) - len(self.text[-1].lstrip())

    # Size of a tab. If set to zero, tabs are not generated.
    _tabsize = 0

    # The output file, or, alternatively, stdout.
    out = sys.stdout

    # This is ribosome call stack. At each level there is a list of
    # text blocks generated up to that point.
    stack = [[]]

    # Redirects output to the specified file.
    @staticmethod
    def output(filename):
        Block.close()
        Block.out = open(filename, "w")
    
    # Redirects output to the specified file.
    # New stuff is added to the existing content of the file.
    @staticmethod
    def append(filename):
        Block.close()
        Block.out = open(filename, "a")

    # Redirect output to the stdout.
    @staticmethod
    def stdout():
        Block.close()
        Block.out = sys.stdout

    # Sets the size of the tab
    @staticmethod
    def tabsize(size):
        Block._tabsize = size

    # Flush the data to the currently open file and close it.
    @staticmethod
    def close():
        for b in Block.stack[-1]:
            b.write(Block.out, Block._tabsize)
        Block.stack = [[]]
        if Block.out is not sys.stdout:
            Block.out.close()

    # Adds one . line from the DNA file.
    @staticmethod
    def add(line, bind=None):

        # If there is no previous line, add one.
        if(len(Block.stack[-1]) == 0):
            Block.stack[-1].append(Block(''))

        # In this block we will accumulate the expanded line.
        block = Block.stack[-1][-1]

        # Traverse the line and convert it into a block.
        i = 0
        while True:
            j = re.search(r'[@&][1-9]?\{', line[i:])
            j = len(line) if j == None else j.start()+i

            # Process constant blocks of text.
            if i != j:
                block.add_right(Block(line[i:j]))

            if len(line) == j: break

            # Process an embedded expression
            i = j
            j += 1
            level = 0
            if line[j] in [str(x) for x in range(1, 10)]:
                level = int(line[j])
                j += 1
            # Find corresponding }.
            par = 0
            while True:
                if line[j] == '{':
                    par += 1
                elif line[j] == '}':
                    par -= 1
                if par == 0: break
                j += 1
                if j >= len(line):
                    raise Exception('Unmatched {')
       
            # Expression of higher indirection levels are simply brought
            # down by one level.
            if level > 0:
                if line[i+1] == '1':
                    block.add_right(Block('@' + line[(i+2):(j+1)]))
                else:
                    ll = list(line)
                    ll[i+1] = str(int(ll[i+1]) - 1)
                    line = ''.join(ll)
                    block.add_right(Block(line[i:(j+1)]))
                i = j + 1
                continue
            # We are at the lowest level of embeddedness so we have to
            # evaluate the embedded expression straight away.
            idx = i+2 if level == 0 else i+3
            expr = line[idx:j]
            Block.stack.append([])
            val = eval(expr, globals(), bind or inspect.currentframe().f_back.f_locals)
            top = Block.stack.pop()
            if len(top) == 0:
                val = Block(str(val))
            else:
                val = Block("")
                for b in top:
                    val.add_bottom(b)
            if line[i] == '@': val.trim()
            block.add_right(val)
            i = j + 1
    
    # Adds newline followed by one . line from the DNA file.
    @staticmethod
    def dot(line, bind=None):
        Block.stack[-1].append(Block(''))
        Block.add(line, bind or inspect.currentframe().f_back.f_locals)

    # Adds newline followed by leading whitespaces copied from the previous line
    # and one line from the DNA file.
    @staticmethod
    def align(line, bind=None):
        if len(Block.stack[-1]) == 0:
            n = 0
        else:
            n = Block.stack[-1][-1].last_offset()
        Block.stack[-1].append(Block(''))
        Block.add(' ' * n, None)
        Block.add(line, bind or inspect.currentframe().f_back.f_locals)


_separate_state = {}
def separate(sep, sid, add):
    global _separate_state
    if not _separate_state.get(sid):
        _separate_state[sid] = True
    else:
        add(sep)

            
def include(file_or_name, warnctx=None, glo=None):
    caller_f = inspect.currentframe().f_back
    filename = caller_f.f_locals['filename']
    lineno = caller_f.f_lineno
    def newwarnctx():
        if warnctx:
            warnctx(s)
        print('At {}:{}'.format(filename, lineno), file=sys.stderr)
    includefile = open(file_or_name, 'r') if type(file_or_name) is str else file_or_name
    glo = glo or caller_f.f_locals['glo'] #FIXME dirty hack
    with includefile as f:
        tree = parse_lines(includefile.name, includefile.readlines(), newwarnctx)
        code = compile(tree, includefile.name, 'exec')
        exec(code, glo, inspect.currentframe().f_back.f_locals)

def parse_lines(filename, lines, warnctx):
    def warn(s):
        # We are not using nonlocal here for python2 compatibility
        caller_f = inspect.currentframe().f_back
        filename = caller_f.f_locals['filename']
        lineno = caller_f.f_lineno
        rawline = caller_f.f_locals['rawline']
        warnctx()
        print('From {}:{}'.format(__file__, inspect.currentframe().f_back.f_lineno), file=sys.stderr)
        print(templ(s, 2), file=sys.stderr)
        print('> '+rawline, file=sys.stderr)

    code = []
    for lineno,rawline in enumerate(lines):
        indent,     dot,     shortcmd,    line,   rspace,     dollar = re.match(
        r'^([\s]*)'+r'(\.?)'+r'(/[+=!])?'+r'(.*?)'+r'([\s]*?)'+r'(\$?)\n?$', rawline).groups()

        # @alixedi - Now that we are doing this in Python, we must have some way
        # of dealing with indentation - for instance, this does not work:
        # for i in [1, 2, 3]:
        # .    @{i}
        # Neither does this work:
        # for i in [1, 2, 3]:
        #     .@{i}
        # I want to be able to support the former.

        if rspace and not dollar:
            warn('Trailing space in line not dollar-terminated')

        if '\t' in rawline:
            # Tabs may cause issues with python's indentation processing
            warn('Line contains tabs. Consider using spaces instead.')

        if not dot:
            code.append(rawline)
            continue

        if not shortcmd:
            cmd, args = 'dot', repr(line)
        elif shortcmd == '/+': # Append the line to the previous line.
            cmd, args = 'add', repr(line)
        elif shortcmd == '/=': # /= Align the line with the previous line.
            cmd, args = 'align', repr(line)
        else:
            m = re.match(r'(^[0-9A-Za-z_]+)\((.*)\)$', line)
            if not m:
                warn('Invalid command syntax. Expected: /!command(arg, etc)')
                code.append('# Invalid command syntax: {}'.format(rawline))
                continue
            cmd, args = m.groups()
        code.append(templ('{indent}{cmd}({args})'))

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
    glo = globals().copy()
    glo.update({
        'output':  Block.output,
        'append':  Block.append,
        'stdout':  Block.stdout,
        'tabsize': Block.tabsize,
        'close':   Block.close,
        'add':     Block.add,
        'dot':     Block.dot,
        'align':   Block.align})
    
    filename = '<ribosome>'
    lineno = 0
    include(f, glo=glo)
    Block.close()

if __name__ == '__main__':
    # Set up the arguments parser.
    import argparse
    parser = argparse.ArgumentParser(prog="ribosome code generator, version 1.16")
    parser.add_argument('dna', type=argparse.FileType('r'), default=sys.stdin)
    args = parser.parse_args()
    runfile(args.dna)

