# -*- coding: UTF-8 -*-


import re
import codecs
import random
from Config import Settings
from itertools import *
from PyQt4.QtCore import *

abbreviations = {
        '1', '10', '11', '12', '2', '3', '4', '5', '6', '7', '8', '9',
        'Ala', 'Alta', 'Ariz', 'Ark', 'Cal', 'Calif', 'Col', 'Colo', 'Conn',
        'Dak', 'Del', 'Fed', 'Fla', 'Ga', 'Ia', 'Id', 'Ida', 'Ill', 'Ind',
        'Is', 'Kan', 'Kans', 'Ken', 'Ky', 'La', 'Man', 'Mass', 'Md', 'Me',
        'Mex', 'Mich', 'Minn', 'Miss', 'Mo', 'Mont', 'Neb', 'Nebr', 'Nev',
        'Ok', 'Okla', 'Ont', 'Ore', 'Pa', 'Penn', 'Penna', 'Qué', 'Sask',
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

class SentenceSplitter(object):
    def __init__(self, text):
        self.string = text

    def __iter__(self):
        p = [0]
        sen = r"""(?:(?: |^)[^\w. ]*(?P<pre>\w+)[^ .]*\.+|[?!]+)['"]?(?= +(?:[^ a-z]|$))|$"""
        sen_re = re.compile(sen)
        return filter(None, map(lambda x: self.pars(p, x), self.sen.finditer(self.string)))

    def pars(self, p, mat):
        is_abbr = lambda s: s.lower() in abbreviations or s in abbreviations
        if mat.group('pre') and is_abbr(mat.group('pre')):
            return None
        p.append(mat.end())
        return self.string[p[-2]:p[-1]].strip()

class LessonMiner(QObject):
    def __init__(self, fname):
        super(LessonMiner, self).__init__()
        #print time.clock()
        with codecs.open(fname, "r", "utf_8_sig") as file:
            self.paras = self.get_paras(file)
        self.lessons = None
        self.min_chars = Settings.get('min_chars')

    def doIt(self):
        self.lessons = []
        backlog = []
        backlen = 0
        i = 0
        for par in self.paras:
            if backlog:
                backlog.append(None)
            for sent in par:
                backlog.append(sent)
                backlen += len(sent)
                if backlen >= self.min_chars:
                    self.lessons.append(self.popFormat(backlog))
                    backlen = 0
            i += 1
            self.emit(SIGNAL("progress(int)"), int(100 * i/len(self.paras)))
        if backlen > 0:
            self.lessons.append(self.popFormat(backlog))

    def popFormat(self, lst):
        #print lst
        ret = []
        part = []
        while lst:
            item = lst.pop(0)
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
            self.doIt()
        return iter(self.lessons)

    def get_paras(self, file):
        p = []
        ps = []
        for line in file:
            line = line.strip()
            if line != '':
                p.append(line)
            elif p:
                ps.append(SentenceSplitter(" ".join(p)))
                p = []
        if p:
            ps.append(SentenceSplitter(" ".join(p)))
        return ps

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
            if idx != -1:
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
    if backlen > 0:
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
        print("--%s--" % x)
