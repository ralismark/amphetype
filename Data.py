#!/usr/bin/env python3

import bisect
import sqlite3
import re

import GtkUtil
from Config import Settings, database_path

def trimmed_average(total, series):
    s_val = 0.0
    n_val = 0

    start = 0
    cutoff = total // 3
    while cutoff > 0:
        cutoff -= series[start][1]
        start += 1
    if cutoff < 0:
        s_val += -cutoff * series[start-1][0]
        n_val += -cutoff

    end = len(series)-1
    cutoff = total // 3
    while cutoff > 0:
        cutoff -= series[end][1]
        end -= 1
    if cutoff < 0:
        s_val += -cutoff * series[end+1][0]
        n_val += -cutoff

    while start <= end:
        s_val += series[start][1] * series[start][0]
        n_val += series[start][1]
        start += 1

    return s_val/n_val

class Statistic(list):
    def __init__(self):
        super(Statistic, self).__init__()
        self.flawed_ = 0

    def append(self, x, flawed=False):
        bisect.insort(self, x)
        if flawed:
            self.flawed_ += 1

    def __cmp__(self, other):
        cmp = lambda a, b: (a > b) - (b > a)
        return cmp(self.median(), other.median())

    def measurement(self):
        return trimmed_average(len(self), [(x, 1) for x in self])

    def median(self):
        length = len(self)
        if length == 0:
            return None
        if length & 1:
            return self[length // 2]
        return (self[length//2] + self[length//2-1])/2.0

    def flawed(self):
        return self.flawed_

class MedianAggregate(Statistic):
    def step(self, val):
        self.append(val)

    def finalize(self):
        return self.median()

class MeanAggregate():
    def __init__(self):
        self.sum_ = 0.0
        self.count_ = 0

    def step(self, value, count):
        self.sum_ += value * count
        self.count_ += count

    def finalize(self):
        return self.sum_ / self.count_

class FirstAggregate():
    def __init__(self):
        self.val = None

    def step(self, val):
        if self.val is not None:
            self.val = val

    def finalize(self):
        return self.val


class AmphDatabase(sqlite3.Connection):
    def __init__(self, *args):
        super(AmphDatabase, self).__init__(*args)

        self.set_regex("")
        self.reset_counter()
        self.lasttime_ = 0.0 # to suppress warning
        self.reset_time_group()
        self.create_function("counter", 0, self.counter)
        self.create_function("regex_match", 1, self.match)
        self.create_function("abbreviate", 2, self.abbreviate)
        self.create_function("time_group", 2, self.time_group)
        self.create_aggregate("agg_median", 1, MedianAggregate)
        self.create_aggregate("agg_mean", 2, MeanAggregate)
        self.create_aggregate("agg_first", 1, FirstAggregate)
        #self.create_aggregate("agg_trimavg", 2, TrimmedAverarge)
        self.create_function("ifelse", 3, lambda x, y, z: y if x is not None else z)

        try:
            self.fetchall("select * from result,source,statistic,text,mistake limit 1")
        except sqlite3.Error:
            self.initialise()

    def reset_time_group(self):
        self.lasttime_ = 0.0
        self.timecnt_ = 0

    def time_group(self, interval, ltime):
        if abs(ltime - self.lasttime_) >= interval:
            self.timecnt_ += 1
        self.lasttime_ = ltime
        return self.timecnt_

    def set_regex(self, pattern):
        self.regex_ = re.compile(pattern)

    def abbreviate(self, string, maxlen):
        if len(string) <= maxlen:
            return string
        return string[:maxlen-3] + "..."

    def match(self, string):
        if self.regex_.search(string):
            return 1
        return 0

    def counter(self):
        self._count += 1
        return self._count

    def reset_counter(self):
        self._count = -1

    def initialise(self):
        self.executescript("""
create table source (name text, disabled integer, discount integer);
create table text (id text primary key, source integer, text text, disabled integer);
create table result (w real, text_id text, source integer, wpm real, accuracy real, viscosity real);
create table statistic (w real, data text, type integer, time real, count integer, mistakes integer, viscosity real);
create table mistake (w real, target text, mistake text, count integer);
create view text_source as
    select id,s.name,text,coalesce(t.disabled,s.disabled)
        from text as t left join source as s on (t.source = s.rowid);
        """)
        self.commit()

    def fetchall(self, *args):
        return self.execute(*args).fetchall()

    def fetchone(self, sql, default, *args):
        row = self.execute(sql, *args).fetchone()
        if row is None:
            return default
        return row

    def get_source(self, source, lesson=None):
        srcids = self.fetchall('select rowid from source where name = ? limit 1', (source, ))
        if srcids:
            self.execute('update source set disabled = NULL where rowid = ?', srcids[0])
            self.commit()
            return srcids[0][0]
        self.execute('insert into source (name,discount) values (?,?)', (source, lesson))
        return self.get_source(source)

# GLOBAL
DB = sqlite3.connect(database_path(), 5, 0, "DEFERRED", False, AmphDatabase)

def switchdb(newfile):
    global DB
    DB.commit()
    try:
        DB = sqlite3.connect(newfile, 5, 0, "DEFERRED", False, AmphDatabase)
    except Exception as e:
        GtkUtil.show_dialog("Database Error", "Failed to switch to the new database:\n" + str(e))
