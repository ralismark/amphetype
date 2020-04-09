#!/usr/bin/env python3

import argparse

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from Config import Settings, PreferenceWidget
from Data import DB
from Quizzer import Quizzer
from StatWidgets import StringStats
from TextManager import TextManager
from Performance import PerformanceHistory
from Lesson import LessonGenerator
from Database import DatabaseWidget

class App(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)
        self.set_title("Amphetype")

        notebook = Gtk.Notebook()
        self.add(notebook)

        quiz = Quizzer()
        notebook.append_page(quiz, Gtk.Label.new("Typer"))

        textm = TextManager()
        notebook.append_page(textm, Gtk.Label.new("Sources"))
        quiz.connect("want-text", lambda _: textm.next_text())
        textm.connect("set-text", lambda _, *text: quiz.set_target(text))
        textm.connect("go-to-text", lambda _: notebook.set_current_page(0))

        perf = PerformanceHistory()
        notebook.append_page(perf, Gtk.Label.new("Performance"))
        textm.connect("refresh-sources", lambda _: perf.refresh_sources())
        quiz.connect("stats-changed", lambda _: perf.update_data())
        perf.connect("set-text", lambda *text: quiz.set_target(text))
        perf.connect("go-to-text", lambda _: notebook.set_current_page(0))

        stats = StringStats()
        notebook.append_page(stats, Gtk.Label.new("Analysis"))
        # stats.connect("lesson-strings", lambda _: notebook.set_current_page(4))

        lgen = LessonGenerator()
        notebook.append_page(lgen, Gtk.Label.new("Lesson Generator"))
        # stats.connect("lesson-strings", lgen.add_strings)
        lgen.connect("new-lessons", lambda _, _2: notebook.set_current_page(1))
        lgen.connect("new-lessons", textm.add_texts)
        # quiz.connect("want-review", ...)
        lgen.connect("new-review", textm.new_review)

        dbase = DatabaseWidget()
        notebook.append_page(dbase, Gtk.Label.new("Database"))

        pref = PreferenceWidget()
        notebook.append_page(pref, Gtk.Label.new("Preferences"))

        textm.next_text()

def main():
    app = App()
    app.show_all()
    app.connect("destroy", Gtk.main_quit)
    Gtk.main()
    DB.commit()

if __name__ == "__main__":
    main()
