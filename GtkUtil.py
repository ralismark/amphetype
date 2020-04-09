#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

def new_button(label, callback):
    widget = Gtk.Button.new_with_label(label)
    widget.connect("clicked", lambda _: callback())
    return widget

def new_label(text, wrap=True):
    return Gtk.Label(label=text, wrap=wrap, use_markup=True, xalign=0)

class AmphBoxLayout(Gtk.Box):
    def __init__(self, layout=None, orientation=Gtk.Orientation.VERTICAL, spacing=8):
        Gtk.Box.__init__(self, orientation=orientation, spacing=spacing)
        self.add_to_back = False

        if layout is not None:
            self.append_layout(layout)

    def append_layout(self, layout):
        for item in layout:
            pack_args = (False, False, 0)
            if isinstance(item, tuple):
                pack_args = (True, True, 0)
                item = item[0]
            widget = self.inflate(item)
            if widget is None:
                continue
            if self.add_to_back:
                self.pack_end(widget, *pack_args)
            else:
                self.pack_start(widget, *pack_args)

    def child_orientation(self):
        if self.get_orientation() == Gtk.Orientation.VERTICAL:
            return Gtk.Orientation.HORIZONTAL
        return Gtk.Orientation.VERTICAL

    def inflate(self, item):
        if isinstance(item, Gtk.Widget):
            return item
        elif isinstance(item, list):
            # nested tree
            return AmphBoxLayout(item, self.child_orientation())
        elif isinstance(item, str):
            # text
            if item and item[-1] == '\n':
                return new_label(item[:-1], True)
            return new_label(item, False)
        elif isinstance(item, int):
            if item == 0:
                return Gtk.Separator.new(self.child_orientation())
            # TODO implement: spacer
            print("inflating int not supported yet")
        elif item is None:
            self.add_to_back = True
        else:
            print("cannot inflate", item)

        return None

class AmphModel(Gtk.ListStore):
    columns = {}

    @staticmethod
    def spec(spec):
        out = {
            "type": None,
            "renderer": str,
            "hidden": False,
            }
        if isinstance(spec, dict):
            out.update(spec)
        else:
            out["type"] = spec
        return out

    def __init__(self):
        Gtk.ListStore.__init__(self)
        self.set_column_types([AmphModel.spec(s)["type"] for s in type(self).columns.values()])

    def set_stats(self, data):
        self.clear()
        for row in data:
            self.append(list(row))

class AmphTreeView(Gtk.ScrolledWindow):
    def __init__(self, model):
        Gtk.ScrolledWindow.__init__(self)
        self.treeview = Gtk.TreeView.new_with_model(model)
        self.add(self.treeview)
        renderer = Gtk.CellRendererText()
        for idx, col in enumerate(type(model).columns.items()):
            name = col[0]
            spec = AmphModel.spec(col[1])
            vcol = Gtk.TreeViewColumn(
                title=name,
                cell_renderer=renderer,
                text=idx)
            if spec["renderer"] is not str:
                datafunc = (lambda col, cell, model, iter, data:
                            cell.set_property("text", data[0](model.get(iter, data[1])[0])))
                vcol.set_cell_data_func(renderer, datafunc, (spec["renderer"], idx))
            if spec["hidden"]:
                vcol.set_visible(False)
            vcol.set_sort_column_id(idx)
            vcol.set_resizable(True)
            self.treeview.append_column(vcol)

def show_dialog(primary, secondary):
    dialog = Gtk.MessageDialog(text=primary, secondary_text=secondary, buttons=Gtk.ButtonsType.OK)
    dialog.run()
    dialog.destroy()

def textbuf_clear(buf):
    buf.delete(*buf.get_bounds())

def textbuf_get_text(buf, include_hidden=True):
    return buf.get_text(*buf.get_bounds(), include_hidden)

def show_in_window(widget):
    win = Gtk.Window()
    win.add(widget)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
