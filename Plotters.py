#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

# TODO implement plotting

class Plot():
    def __init__(self, x, y):
        self.x = x
        self.y = y
        pass

class Plotter(Gtk.Label):
    def __init__(self):
        Gtk.Label.__init__(self, label="not yet implemented")
        self.data = None

    def set_data(self, data):
        self.data = data
