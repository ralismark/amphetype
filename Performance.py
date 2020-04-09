#!/usr/bin/env python3

import time

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject

import GtkUtil
from Data import DB
from Config import Settings, SettingsEdit, SettingsCombo, SettingsCheckBox
import Plotters

def dampen(seq, window=10):
    total = sum(seq[:window])
    for i in range(window, len(seq)):
        yield total/window
        total += seq[i] - seq[i-window]

def format_when(when):
    delta = time.time() - when

    if delta < 60.0:
        return f"{delta:.1f}s"
    delta /= 60.0
    if delta < 60.0:
        return f"{delta:.1f}m"
    delta /= 60.0
    if delta < 24.0:
        return f"{delta:.1f}h"
    delta /= 24.0
    if delta < 7.0:
        return f"{delta:.1f}d"
    delta /= 7.0
    if delta < 52.0:
        return f"{delta:.1f}w"
    delta /= 52.0
    return f"{delta:.1f}y"

class ResultModel(GtkUtil.AmphModel):
    columns = {
        "ID": {
            "type": str,
            "hidden": True,
            },
        "When": {
            "type": float,
            "renderer": format_when,
            },
        "Source": str,
        "WPM": {
            "type": float,
            "renderer": "{:.2f}".format,
            },
        "Accuracy (%)": float,
        "Viscosity": float,
        }

class PerformanceHistory(GtkUtil.AmphBoxLayout):
    __gsignals__ = {
        "go-to-text": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "set-text": (GObject.SignalFlags.RUN_FIRST, None, (str, int, str)),
        }

    def __init__(self):
        GtkUtil.AmphBoxLayout.__init__(self)

        self.plotcol = 3
        self.plot = Plotters.Plotter()

        self.editflag = False
        self.model = ResultModel()

        self.cb_source = Gtk.ComboBoxText()
        self.refresh_sources()
        self.cb_source.set_active_id("all")
        self.cb_source.connect("changed", lambda _: self.update_data())

        tree = GtkUtil.AmphTreeView(self.model)
        tree.treeview.connect("row-activated", self.double_clicked)
        Settings.on_any_change(["graph_what", "show_xaxis", "chrono_x", "dampen_graph"],
                               self.update_graph)
        Settings.on_any_change(["perf_items", "perf_group_by", "lesson_stats"], self.update_data)

        self.append_layout([
            ["Show", SettingsEdit("perf_items"), "items from", self.cb_source,
             "and group by", SettingsCombo("perf_group_by", [
                 "<no grouping>", "%d sessions" % Settings.get("def_group_by"), "sitting", "day"]),
             None, GtkUtil.new_button("Update", self.update_data)],
            (tree, ),
            ["Plot", SettingsCombo("graph_what", ((3, "WPM"), (4, "accuracy"), (5, "viscosity"))),
             SettingsCheckBox("show_xaxis", "Show X-axis"),
             SettingsCheckBox("chrono_x", "Use time-scaled X-axis"),
             SettingsCheckBox("dampen_graph", "Dampen graph values")],
            (self.plot, ),
            ])

        self.update_data()

    def update_graph(self):
        what = Settings.get("graph_what")
        y_coords = [row[what] for row in iter(self.model)]

        if Settings.get("chrono_x"):
            x_coords = [row[0] for row in iter(self.model)]
        else:
            x_coords = list(range(len(y_coords)-1, 0-1, -1))

        if Settings.get("dampen_graph"):
            window = Settings.get("dampen_average")
            y_coords = list(dampen(y_coords, window))
            x_coords = list(dampen(x_coords, window))

        plot = Plotters.Plot(x_coords, y_coords)
        self.plot.set_data(plot)

    def refresh_sources(self):
        self.editflag = True
        self.cb_source.remove_all()
        self.cb_source.append("all", "<ALL>")
        self.cb_source.append("last text", "<LAST TEXT>")
        self.cb_source.append("all texts", "<ALL TEXTS>")
        self.cb_source.append("all lessons", "<ALL LESSONS>")
        for rid, label in DB.fetchall("select rowid,abbreviate(name,30) from source order by name"):
            self.cb_source.append(str(rid), label)
        self.editflag = False

    def update_data(self):
        if self.editflag:
            return
        where = []
        where_query = ""
        selected = self.cb_source.get_active_id()
        if selected == "last text":
            where.append("r.text_id = (select text_id from result order by w desc limit 1)")
        elif selected == "all texts":
            where.append("s.discount is null")
        elif selected == "all lessons":
            where.append("s.discount is not null")
        elif selected and selected.isdigit():
            rowid = int(selected)
            where.append(f"r.source = {rowid}")

        if where:
            where_query = "where " + " and ".join(where)

        sql_template = """select agg_first(text_id),avg(r.w) as w,count(r.rowid)
                || ' result(s)',agg_median(r.wpm),
                100.0*agg_median(r.accuracy),agg_median(r.viscosity)
            from result as r left join source as s on (r.source = s.rowid)
            %s %s
            order by w desc limit %d"""

        groupby = Settings.get("perf_group_by")
        group = ""
        print(groupby)
        if groupby == 1: # by def_group_by
            DB.reset_counter()
            group = "group by cast(counter()/%d as int)" % max(Settings.get("def_group_by"), 1)
        elif groupby == 2: # by sitting
            mis = Settings.get("minutes_in_sitting") * 60.0
            DB.reset_time_group()
            group = "group by time_group(%f, r.w)" % mis
        elif groupby == 3: # by day
            group = "group by cast((r.w+4*3600)/86400 as int)"
        elif not groupby: # no grouping
            sql_template = """select text_id,w,s.name,wpm,100.0*accuracy,viscosity
                from result as r left join source as s on (r.source = s.rowid)
                %s %s
                order by w desc limit %d"""

        items = Settings.get("perf_items")

        sql = sql_template % (where_query, group, items)
        self.model.set_stats([list(r) for r in DB.fetchall(sql)])
        self.update_graph()

    def double_clicked(self, treeview, where, _column):
        row = Gtk.TreeModelRow(treeview.get_model(), where)
        target = DB.fetchone("select id,source,text from text where id = ?", None, (row[0], ))
        if target is None:
            return
        self.emit("set-text", *target)
        self.emit("go-to-text")

if __name__ == "__main__":
    GtkUtil.show_in_window(PerformanceHistory())
