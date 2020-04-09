#!/usr/bin/env python3

import re
import codecs
import random

import gi
from gi.repository import GObject

from Config import Settings

abbreviations = {
        '1', '10', '11', '12', '2', '3', '4', '5', '6', '7', '8', '9',
        'Ala', 'Alta', 'Ariz', 'Ark', 'Cal', 'Calif', 'Col', 'Colo', 'Conn',
        'Dak', 'Del', 'Fed', 'Fla', 'Ga', 'Ia', 'Id', 'Ida', 'Ill', 'Ind',
        'Is', 'Kan', 'Kans', 'Ken', 'Ky', 'La', 'Man', 'Mass', 'Md', 'Me',
        'Mex', 'Mich', 'Minn', 'Miss', 'Mo', 'Mont', 'Neb', 'Nebr', 'Nev',
        'Ok', 'Okla', 'Ont', 'Ore', 'Pa', 'Penn', 'Penna', 'Que', 'Sask',
        'Tenn', 'Tex', 'USAFA', 'Ut', 'Va', 'Vt', 'Wash', 'Wis', 'Wisc', 'Wy',
        'Wyo', 'Yuk', 'adm', 'al', 'apr', 'arc', 'assn', 'atty', 'attys',
        'aug', 'ave', 'avg', 'bld', 'blvd', 'bros', 'capt', 'cl', 'cmdr', 'co',
        'col', 'corp', 'cpl', 'cres', 'ct', 'dec', 'dept', 'det', 'dist', 'dr',
        'eg', 'esp', 'etc', 'exp', 'expy', 'feb', 'ft', 'fwy', 'fy', 'gen',
        'gov', 'hway', 'hwy', 'ie', 'inc', 'jan', 'jr', 'jul', 'jun', 'la',
        'lt', 'ltd', 'm', 'maj', 'mar', 'may', 'mme', 'mr', 'mrs', 'ms', 'mt',
        'no', 'nov', 'oct', 'pd', 'pde', 'pl', 'plz', 'prof', 'rd', 'rep',
        'reps', 'rev', 'sen', 'sens', 'sep', 'sept', 'sgt', 'sr', 'st', 'supt',
        'tce', 'univ', 'viz', 'vs'
        }

class SentenceSplitter():
    def __init__(self, text):
        self.string = text

    def __iter__(self):
        parts = [0]
        sentence = r"""(?:(?: |^)[^\w. ]*(?P<pre>\w+)[^ .]*\.+|[?!]+)['"]?(?= +(?:[^ a-z]|$))|$"""
        sen_re = re.compile(sentence)
        return filter(None, [self.pars(parts, x) for x in sen_re.finditer(self.string)])

    def pars(self, parts, mat):
        is_abbr = lambda s: s.lower() in abbreviations or s in abbreviations
        if mat.group('pre') and is_abbr(mat.group('pre')):
            return None
        parts.append(mat.end())
        return self.string[parts[-2]:parts[-1]].strip()

class LessonMiner(GObject.Object):
    __gsignals__ = {
        'progress': (GObject.SignalFlags.RUN_FIRST, None, (int, ))
        }

    def __init__(self, fname):
        GObject.Object.__init__(self)
        with codecs.open(fname, "r", "utf_8_sig") as file:
            self.paras = self.get_paras(file)
        self.lessons = None
        self.min_chars = Settings.get("min_chars")

    def generate_lessons(self):
        self.lessons = []
        backlog = []
        backlen = 0
        for i, par in enumerate(self.paras):
            if backlog:
                backlog.append(None)

            for sentence in par:
                backlog.append(sentence)
                backlen += len(sentence)
                if backlen >= self.min_chars:
                    self.lessons.append(self.format(backlog))
                    backlog = []
                    backlen = 0

            self.emit("progress", 100 * i // len(self.paras))
        if backlen:
            self.lessons.append(self.format(backlog))

    def format(self, fragments):
        ret = []
        part = []
        for item in fragments:
            if item is not None:
                part.append(item)
            else:
                ret.append(' '.join(part))
                part = []

        if part:
            ret.append(' '.join(part))
        return '\n'.join(ret)

    def __iter__(self):
        if self.lessons is None:
            self.generate_lessons()
        return iter(self.lessons)

    def get_paras(self, file):
        partial = []
        output = []
        for line in file:
            line = line.strip()
            if line:
                partial.append(line)
            elif partial:
                output.append(SentenceSplitter(" ".join(partial)))
                partial = []
        if partial:
            output.append(SentenceSplitter(" ".join(partial)))
        return output

def to_lessons(sentences):
    backlog = []
    backlen = 0
    min_chars = Settings.get('min_chars')
    max_chars = Settings.get('max_chars')
    sweet_size = 3*(min_chars + max_chars) // 4

    for sent in sentences:
        ssplit = []
        while len(sent) > sweet_size:
            idx = sent.find(' ', sweet_size)
            if idx == -1:
                break
            ssplit.append(sent[:idx])
            sent = sent[idx+1:]

        ssplit.append(sent)
        for part in ssplit:
            backlog.append(part)
            backlen += len(part)
            if backlen >= min_chars:
                yield ' '.join(backlog)
                backlog = []
                backlen = 0

    if backlen:
        yield ' '.join(backlog)

class LessonGeneratorPlain():
    def __init__(self, words, per_lesson=12, repeats=4):
        while 0 < len(words) % per_lesson < per_lesson / 2:
            per_lesson += 1

        self.lessons = []
        wcopy = words[:]
        while wcopy:
            lesson = wcopy[0:per_lesson] * repeats
            wcopy[0:per_lesson] = []
            random.shuffle(lesson)
            self.lessons.append( #textwrap.fill(
                ' '.join(lesson)) #, width))

    def __iter__(self):
        return iter(self.lessons)

if __name__ == '__main__':
    import sys
    for x in LessonMiner(sys.argv[1]):
        print(f"--{x}--")
