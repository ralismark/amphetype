#!/usr/bin/env python3

import collections
from time import time as timer
import re

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GObject, Pango

from Data import Statistic, DB
from Config import Settings
import GtkUtil

def get_wait_text():
    if Settings.get("req_space"):
        return ("Press SPACE and then immediately start typing the text\n"
                "Press ESCAPE to restart with a new text at any time")
    return "Press ESCAPE to restart with a new text at any time"


class Typer(Gtk.TextView):
    __gsignals__ = {
        "done": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "want-text": (GObject.SignalFlags.RUN_FIRST, None, ()),
        }

    def __init__(self):
        Gtk.TextView.__init__(self, wrap_mode=Gtk.WrapMode.WORD)

        sync_font = lambda: self.override_font(
            Pango.FontDescription.from_string(Settings.get("typer_font")))
        sync_font()

        self.connect("key-press-event", lambda _, key: self.key_press(key))
        self.get_buffer().connect("end-user-action", lambda _: self.check_text())
        Settings.on_any_change([
            "quiz_wrong_fg",
            "quiz_wrong_bg",
            "quiz_right_fg",
            "quiz_right_bg",
            ], self.update_palette)
        Settings.on_any_change(["typer_font"], sync_font)

        self.set_target("") # clear input

    def key_press(self, key):
        if Gdk.keyval_name(key.keyval) == "Escape":
            self.emit("want-text")
            return True
        return False

    def set_target(self, text):
        self.edit_flag = True
        self.target = text
        self.when = [0] * (len(text) + 1)
        self.times = [0] * len(text)
        self.mistake = [False] * len(text)
        self.mistakes = {}
        self.where = 0

        self.get_buffer().set_text(get_wait_text(), -1)
        self.get_buffer().select_range(*self.get_buffer().get_bounds())
        self.edit_flag = False

    def check_text(self):
        if not self.target or self.edit_flag:
            return

        text = GtkUtil.textbuf_get_text(self.get_buffer())
        if self.when[0] == 0: # We're just starting
            space = text and text[-1] == " "

            self.edit_flag = True
            if space:
                self.when[0] = timer()
                self.get_buffer().set_text("", -1)
                self.update_palette("right")
            elif Settings.get("req_space"): # reset
                self.get_buffer().set_text(get_wait_text(), -1)
                self.get_buffer().select_range(*self.get_buffer().get_bounds())

            self.edit_flag = False

            if space or Settings.get("req_space"):
                return
            self.when[0] = -1

        # find first difference
        for upto in range(min(len(text), len(self.target))):
            if text[upto] != self.target[upto]:
                break
        else:
            upto = min(len(text), len(self.target))
        self.where = upto

        if self.when[upto] == 0 and upto == len(text):
            self.when[upto] = timer()
            if upto:
                self.times[upto-1] = self.when[upto] - self.when[upto-1]

        if upto == len(self.target):
            self.emit("done")
            return

        if upto < len(text) and upto < len(self.target):
            self.mistake[upto] = True
            self.mistakes[upto] = self.target[upto] + text[upto]

        self.update_palette("right" if upto == len(text) else "wrong")

    def get_mistakes(self):
        inv = collections.defaultdict(lambda: 0)
        for mistake in self.mistakes.values():
            inv[mistake] += 1
        return inv

    def get_stats(self):
        if self.when[0] == -1:
            times = sorted(self.times[1:], reverse=True)
            self.times[0] = DB.fetchone(
                "select time from statistic where type=0 and data=? order by rowid desc limit 1",
                (times[len(times)//5], ), (self.target[0], ))[0]
            self.when[0] = self.when[1] - self.times[0]
        return (self.when[self.where] - self.when[0], self.where, self.times,
                self.mistake, self.get_mistakes())

    def update_palette(self, which=None):
        # TODO use configured colors
        if which == "right":
            self.override_color(Gtk.StateFlags.NORMAL, None)
        elif which == "wrong":
            self.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(1.0, 0.0, 0.0))

class Quizzer(Gtk.Box):
    __gsignals__ = {
        "want-text": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "stats-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        }

    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        self.result = Gtk.Label()
        self.typer = Typer()
        self.label = Gtk.Label(wrap=True, xalign=0, yalign=1)

        update_result_vis = lambda: self.result.set_visible(Settings.get("show_last"))
        update_result_vis()

        sync_font = lambda: self.label.override_font(
            Pango.FontDescription.from_string(Settings.get("typer_font")))
        sync_font()

        self.typer.connect("done", lambda *_: self.done())
        self.typer.connect("want-text", lambda *_: self.emit("want-text"))
        Settings.connect("change_typer_font", sync_font)
        Settings.connect("change_show_last", update_result_vis)

        self.text = ("", 0, "")

        self.pack_start(self.result, False, False, 0)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, homogeneous=True, spacing=24)
        body.add(self.label)
        body.add(self.typer)
        self.pack_start(body, True, True, 0)

    def set_target(self, text):
        self.text = text
        self.label.set_text(text[2].replace("\n", "↵\n"))
        self.typer.set_target(self.text[2])
        self.typer.grab_focus()

    def done(self):
        print("DONE")
        # TODO split into smaller bits
        now = timer()
        elapsed, chars, times, mis, mistakes = self.typer.get_stats()
        text = self.text[2]

        assert chars == len(text)

        accuracy = 1.0 - sum(1 for f in mis if f) / chars
        spc = elapsed / chars
        viscosity = sum((t / spc - 1) ** 2 for t in times) / chars

        DB.execute("""insert into result (w, text_id, source, wpm, accuracy, viscosity)
                   values (?,?,?,?,?,?)""",
                   (now, self.text[0], self.text[1], 12.0/spc, accuracy, viscosity))

        wpm_median, acc_median = DB.fetchone(f"""select agg_median(wpm),agg_median(acc) from
            (select wpm,100.0*accuracy as acc from result order by w desc limit
             {Settings.get("def_group_by")})""", (0.0, 100.0))

        self.result.set_text(
            "Last: {:.1f}wpm ({:.1f}%), last 10 average: {:.1f}wpm ({:.1f}%)".format(
                12.0/spc, 100.0*accuracy, wpm_median, acc_median))

        self.emit("stats-changed")

        stats = collections.defaultdict(Statistic)
        viscs = collections.defaultdict(Statistic)

        for char, time, mistake in zip(text, times, mis):
            stats[char].append(time, mistake)
            viscs[char].append((time/spc - 1)**2)

        def gen_tup(start, end):
            span = end - start
            char_avg = sum(times[start:end]) / span
            visc = sum((t/char_avg - 1)**2 for t in times[start:end]) / span
            return (text[start:end], char_avg, sum(1 for f in mis[start:end] if f), visc)

        for trigraph, time, mist, visc in [gen_tup(i, i+3) for i in range(0, chars - 2)]:
            stats[trigraph].append(time, mist > 0)
            viscs[trigraph].append(visc)

        regex = re.compile(r"(\w|'(?![A-Z]))+(-\w(\w|')*)*")
        for word, time, mist, visc in [
                gen_tup(*m.span()) for m in regex.finditer(text) if m.end() - m.start() > 3]:
            stats[word].append(time, mist > 0)
            viscs[word].append(visc)

        def kind(key):
            if len(key) == 1:
                return 0
            if len(key) == 3:
                return 1
            return 2

        vals = []
        for key, stat in stats.items():
            visc = viscs[key].median()
            vals.append((stat.median(), visc*100.0, now, len(stat), stat.flawed(), kind(key), key))

        is_lesson = DB.fetchone("select discount from source where rowid=?",
                                (None,), (self.text[1], ))[0]

        if Settings.get("use_lesson_stats") or not is_lesson:
            DB.executemany("""insert into statistic (time,viscosity,w,count,mistakes,type,data)
                    values (?,?,?,?,?,?,?)""", vals)
            DB.executemany("insert into mistake (w,target,mistake,count) values (?,?,?,?)",
                           [(now, k[0], k[1], v) for k, v in mistakes.items()])

        if is_lesson:
            mins = (Settings.get("min_lesson_wpm"), Settings.get("min_lesson_acc"))
        else:
            mins = (Settings.get("min_wpm"), Settings.get("min_acc"))

        if 12.0/spc < mins[0] or accuracy < mins[1]/100.0:
            self.set_target(self.text)
        elif not is_lesson and Settings.get('auto_review'):
            words = [x for x in vals if x[5] == 2]
            if not words:
                self.emit("want-text")
                return
            words.sort(key=lambda x: (x[4], x[0]), reverse=True)
            i = 0
            while words[i][4] != 0:
                i += 1
            i += (len(words) - i) // 4

            # TODO support want-review
            # self.emit("want-review", [x[6] for x in words[0:i]])
        else:
            self.emit("want-text")

if __name__ == "__main__":
    quizzer = Quizzer()
    quizzer.set_target(("", 0, "This is a sample text!\nRun Amphetype.py for the full program"))
    GtkUtil.show_in_window(quizzer)
