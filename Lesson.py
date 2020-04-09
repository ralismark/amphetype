#!/usr/bin/env python3

import time
import random
import codecs
import itertools

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GObject, GLib, Gtk

import GtkUtil
from Data import DB
from Config import Settings, SettingsEdit, SettingsCombo
import Text

try:
    import editdist
except ImportError:
    import editdist_fake as editdist

class StringListWidget(Gtk.ScrolledWindow):
    __gsignals__ = {
        'updated': (GObject.SignalFlags.RUN_FIRST, None, ())
        }
    def __init__(self):
        Gtk.ScrolledWindow.__init__(self)

        self.textview = Gtk.TextView(
            wrap_mode=Gtk.WrapMode.WORD
            )
        self.delayflag = 0
        self.textview.get_buffer().connect("changed", lambda _: self.text_changed())

        self.add(self.textview)

    def buf(self):
        return self.textview.get_buffer()

    def add_list(self, lines):
        self.buf().insert(self.buf().get_end_iter(), " ".join(lines), -1)

    def get_list(self):
        return GtkUtil.textbuf_get_text(self.buf()).split()

    def add_from_typed(self):
        query = 'select distinct data from statistic where type = 2 order by random()'
        words = [x[0] for x in DB.fetchall(query)]
        self.filter_words(words)

    def add_from_file(self):
        filepicker = Gtk.FileChooserDialog()
        filepicker.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        filepicker.add_button(Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT)
        result = filepicker.run()
        if result == Gtk.ResponseType.CANCEL or filepicker.get_filename() is None:
            filepicker.destroy()
            return

        fname = filepicker.get_filename()
        filepicker.destroy()

        try:
            with codecs.open(fname, "r", "utf_8_sig") as file:
                words = file.read().split()
        except Exception as e:
            GtkUtil.show_dialog("Couldn't Read File", str(e))
            return

        random.shuffle(words)
        self.filter_words(words)

    def filter_words(self, words):
        num = Settings.get('str_extra')
        what = Settings.get('str_what')
        if what == 'r': # random
            pass
        else:
            control = self.get_list()
            if not control:
                return
            if what == 'e': # encompassing
                stream = [(sum([x.count(c) for c in control]), x) for x in words]
                #print "str:", list(stream)[0:10]
                preres = list(itertools.islice(filter(lambda x: x[0] > 0, stream), 4*num))
                #print "pre:", preres
                preres.sort(key=lambda x: x[0], reverse=True)
                words = [x[1] for x in preres]
            else: # similar
                words = filter(lambda x:
                               0 < min(
                                   editdist.distance(
                                       x.encode('latin1', 'replace'),
                                       y.encode('latin1', 'replace'))/max(len(y), len(x))
                                   for y in control) < .26, words)

        if Settings.get('str_clear') == 'r': # replace = clear
            GtkUtil.textbuf_clear(self.buf())

        self.add_list(itertools.islice(words, num))

    def text_changed(self):
        if self.delayflag > 0:
            self.delayflag += 1
            return

        self.emit("updated")
        self.delayflag = 1
        GLib.timeout_add(500, self.revert_flag)

    def revert_flag(self):
        if self.delayflag > 1:
            self.emit("updated")
        self.delayflag = 0
        return False

class LessonGenerator(GtkUtil.AmphBoxLayout):
    __gsignals__ = {
        'new-review': (GObject.SignalFlags.RUN_FIRST, None, (str, )),
        'new-lessons': (GObject.SignalFlags.RUN_FIRST, None, (str, str))
        }

    def __init__(self):
        self.strings = StringListWidget()
        self.sample = Gtk.TextView(
            wrap_mode=Gtk.WrapMode.WORD,
            editable=False
            )
        self.lesson_name_field = Gtk.Entry()

        scroll_sample = Gtk.ScrolledWindow()
        scroll_sample.add(self.sample)
        combo_what = SettingsCombo('str_what',
                                   [('e', 'encompassing'), ('s', 'similar'), ('r', 'random')])
        layout = [
            "Welcome to Amphetype's automatic lesson generator!",

            "You can retrieve a list of words/keys/trigrams to practice from the Analysis tab,"
            " import from an external file, or even type in your own (separated by space).\n",
            10,
            ["In generating lessons, I will make", SettingsEdit("gen_copies"),
             "copies of the list below and divide them into sublists of size",
             SettingsEdit("gen_take"), "(0 for all)"],
            ["I will then", SettingsCombo("gen_mix", [('c', "concatenate"), ('m', "commingle")]),
             "corresponding sublists into atomic building blocks which are fashioned into lessons"
             " according to your lesson size preferences."],
            [["Input words", self.strings, [
                SettingsCombo("str_clear", [('s', "Supplement"), ('r', "Replace")]),
                "list with", SettingsEdit("str_extra"), combo_what, "words from",
                GtkUtil.new_button("a file", self.strings.add_from_file), "or",
                GtkUtil.new_button("analysis database", self.strings.add_from_typed)]],
              ["Lessons", scroll_sample, [
                  GtkUtil.new_button("Add to sources", self.accept_lessons), "with name",
                  self.lesson_name_field]]
             ],
            ]

        GtkUtil.AmphBoxLayout.__init__(self, layout)
        Settings.connect("change_gen_take", lambda: self.generate_preview())
        Settings.connect("change_gen_copies", lambda: self.generate_preview())
        Settings.connect("change_gen_mix", lambda: self.generate_preview())
        self.strings.connect("updated", lambda _: self.generate_preview())

    def want_review(self, words):
        sentences = self.generate_lesson(words)
        self.emit("new-review", " ".join(sentences))

    def generate_preview(self):
        print("updating preview")
        words = self.strings.get_list()
        sentences = self.generate_lesson(words)
        GtkUtil.textbuf_clear(self.sample.get_buffer())
        for lesson in Text.to_lessons(sentences):
            buf = self.sample.get_buffer()
            buf.insert(buf.get_end_iter(), lesson + "\n\n", -1)

    def generate_lesson(self, words):
        copies = Settings.get('gen_copies')
        take = Settings.get('gen_take')
        mix = Settings.get('gen_mix')

        sentences = []
        while words:
            sen = words[:take] * copies
            words[:take] = []

            if mix == 'm': # mingle
                random.shuffle(sen)
            sentences.append(' '.join(sen))
        return sentences

    def accept_lessons(self):
        name = self.lesson_name_field.get_text().strip()
        if not name:
            timestamp = time.strftime("%y-%m-%d %H:%M")
            name = f"<Lesson {timestamp}>"

        lessons = [x.strip() for x in GtkUtil.textbuf_get_text(
            self.sample.get_buffer()).split("\n\n") if x.strip()]

        if not lessons:
            GtkUtil.show_dialog("No Lessons", "Generate some lessons before you try to add them!")
            return

        self.emit("new-lessons", name, lessons.join("\n\n"))

    def add_strings(self, strings):
        self.strings.add_list(strings)

if __name__ == '__main__':
    GtkUtil.show_in_window(LessonGenerator())
