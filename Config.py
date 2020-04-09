#!/usr/bin/env python3

import sys
import os.path
import pickle
import json

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GObject, Gdk, Gtk, GLib

import GtkUtil

def data_path(name):
    config_dir = GLib.get_user_config_dir()
    return os.path.join(config_dir, "Amphetype", name)

def config_path():
    return data_path("Amphetype.json")

def database_path():
    return data_path("typer.db")

class AmphSettings(GObject.Object):
    defaults = {
        "typer_font": "monospace 14",
        "history": 30.0,
        "min_chars": 220,
        "max_chars": 600,
        "lesson_stats": 0, # show text/lesson in perf -- not used anymore
        "perf_group_by": 0,
        "perf_items": 100,
        "text_regex": r"",
        "select_method": 0,
        "num_rand": 50,
        "graph_what": 3,
        "req_space": True,
        "show_last": True,
        "show_xaxis": False,
        "chrono_x": False,
        "dampen_graph": False,

        "minutes_in_sitting": 60.0,
        "dampen_average": 10,
        "def_group_by": 10,

        "use_lesson_stats": False,
        "auto_review": False,

        "min_wpm": 0.0,
        "min_acc": 0.0,
        "min_lesson_wpm": 0.0,
        "min_lesson_acc": 97.0,

        "quiz_right_fg": "#000000",
        "quiz_right_bg": "#ffffff",
        "quiz_wrong_fg": "#ffffff",
        "quiz_wrong_bg": "#000000",

        "group_month": 365.0,
        "group_week": 30.0,
        "group_day": 7.0,

        "ana_which": "wpm asc",
        "ana_what": 0,
        "ana_many": 30,
        "ana_count": 1,

        "gen_copies": 3,
        "gen_take": 2,
        "gen_mix": "c",
        #"gen_stats": False,
        "str_clear": "s",
        "str_extra": 10,
        "str_what": "e"
        }

    __gsignals__ = {
        "change": (GObject.SignalFlags.RUN_FIRST, None, ()),
        **{("change_" + key): (GObject.SignalFlags.RUN_FIRST, None, ()) for key in defaults}
        }

    def __init__(self):
        GObject.Object.__init__(self)
        self.settings = {}
        try:
            with open(config_path()) as cfg:
                self.settings = json.load(cfg)
        except FileNotFoundError:
            pass
        except json.JSONDecodeError:
            print("Config is invalid! Either fix it or remove it")
            print(config_path())
            sys.exit()
        except IOError as err:
            print("Error opening config\n", err)
            print(config_path())
            sys.exit()

    def get(self, key):
        """
        Get configuration value corresponding to a certain key
        """
        value = self.settings.get(key, None)
        # if value:
        #     print("get", key, type(pickle.loads(value)), pickle.loads(value))
        # else:
        #     print("get", key, None)
        if value is None:
            return self.defaults[key]
        return value

    def get_color(self, key):
        """
        Get config value as a RGBA color.
        """
        color = Gdk.RGBA()
        color.parse(self.get(key))
        return color

    def commit(self):
        """
        Save the config to disk
        """
        try:
            with open(config_path(), "w") as cfg:
                json.dump(self.settings, cfg)
        except IOError as err:
            print("Error saving config\n", err)

    def set(self, key, value):
        """
        Set persistent configuration value
        """
        if self.get(key) == value:
            return # nothing changed
        print("set", key, value)
        self.settings[key] = value
        self.commit()
        self.emit("change")
        self.emit("change_" + key)

    def on_any_change(self, configs, callback):
        for key in configs:
            self.connect("change_" + key, lambda *_: callback())

Settings = AmphSettings()

class SettingsColor(Gtk.ColorButton):
    def __init__(self, key, _text):
        # TODO color label
        Gtk.ColorButton.__init__(self, rgba=Settings.get_color(key))
        self.connect("color-set", lambda _: Settings.set(key, self.get_rgba().to_string()))

class SettingsEdit(Gtk.Entry):
    def __init__(self, key):
        val = Settings.get(key)
        typ = type(val)
        # TODO actually use validator
        # Make our own validators
        validator = None
        if isinstance(val, float):
            validator = lambda: None
        elif isinstance(val, int):
            validator = lambda: None
        if validator is None:
            self.fmt = lambda x: x
        else:
            self.fmt = lambda x: "%g" % x

        Gtk.Entry.__init__(self, text=self.fmt(val))
        Settings.connect("change_" + key,
                         lambda: self.set_text(self.fmt(Settings.get(key))))
        self.connect("activate",
                     lambda _: Settings.set(key, typ(self.get_text())))

class SettingsCombo(Gtk.ComboBoxText):
    def __init__(self, key, options):
        Gtk.ComboBoxText.__init__(self)
        prev = Settings.get(key)
        typ = int
        for val, label in enumerate(options):
            if not isinstance(label, str):
                val, label = label # options is a list of pairs
            typ = type(val)
            self.append(str(val), label)
            if val == prev:
                self.set_active_id(str(val))

        self.connect("changed",
                     lambda _: Settings.set(key, typ(self.get_active_id())))

class SettingsCheckBox(Gtk.CheckButton):
    def __init__(self, key, label):
        Gtk.CheckButton.__init__(self, active=bool(Settings.get(key)))
        self.add(Gtk.Label.new(label))
        self.connect("toggled", lambda _: Settings.set(key, self.get_active()))

class PreferenceWidget(GtkUtil.AmphBoxLayout):
    def __init__(self):
        font_button = Gtk.FontButton.new_with_font(Settings.get("typer_font"))
        def fontset():
            Settings.set("typer_font", font_button.get_font())
            print(Settings.get("typer_font"))
        font_button.connect("font-set",
                            lambda _: fontset())

        help_str = '<a href="http://code.google.com/p/amphetype/wiki/Settings">Settings help</a>'

        layout = [
            help_str,
            ["Typer font is ", font_button],
            SettingsCheckBox("auto_review",
                             "Automatically review slow and mistyped words after texts."),
            SettingsCheckBox("show_last", "Show last result(s) above text in the Typer."),
            SettingsCheckBox("use_lesson_stats",
                             "Save key/trigram/word statistics from generated lessons."),
            SettingsCheckBox("req_space", "Make SPACE mandatory before each session"),
            0,
            ["Correct Input", SettingsColor("quiz_right_fg", "Foreground"),
             SettingsColor("quiz_right_bg", "Background")],
            ["Wrong Input", SettingsColor("quiz_wrong_fg", "Foreground"),
             SettingsColor("quiz_wrong_bg", "Background")],
            0,
            ["Data is considered too old to be included in analysis after",
             SettingsEdit("history"), "days."],
            ["Try to limit texts and lessons to between", SettingsEdit("min_chars"),
             "and", SettingsEdit("max_chars"), "characters."],
            ["When selecting easy/difficult texts, scan a sample of",
             SettingsEdit("num_rand"), "texts."],
            ["When grouping by sitting on the Performance tab, consider results more than",
             SettingsEdit("minutes_in_sitting"), "minutes away to be part of a different sitting."],
            ["Group by", SettingsEdit("def_group_by"),
             "results when displaying last scores and showing last results on the Typer tab."],
            ["When smoothing out the graph, display a running average of",
             SettingsEdit("dampen_average"), "values"],
            ]
        GtkUtil.AmphBoxLayout.__init__(self, layout)
        self.set_homogeneous(True)

if __name__ == "__main__":
    GtkUtil.show_in_window(PreferenceWidget())
