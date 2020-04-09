#!/usr/bin/env python3

import time

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from Config import Settings, SettingsEdit
from Data import DB
import GtkUtil

class DatabaseWidget(GtkUtil.AmphBoxLayout):
    def __init__(self):
        GtkUtil.AmphBoxLayout.__init__(self)

        self.stats = GtkUtil.new_label("Press Update to fetch database statistics")
        self.progressbar = Gtk.ProgressBar()

        self.append_layout([
            [GtkUtil.new_button("Update", self.update)],
            0,
            self.stats,
            0,
            "After heavy use for several months the database can grow quite large since lots of"
            " data are generated after every result and it's all stored indefinitely. Here you can"
            " group old statistics into larger batches. This will speed up data retrieval for"
            " statistics. It is recommended you do it once a month or so if you use the program"
            " regularly.\n",
            "Group data older than:\n",
            [SettingsEdit("group_month"), "days into months"],
            [SettingsEdit("group_week"), "days into weeks"],
            [SettingsEdit("group_day"), "days into days"],
            [GtkUtil.new_button("Go!", self.cleanup)],
            None,
            self.progressbar
            ])

    def update(self):
        texts = DB.fetchone("select count(*) from text", (0,))[0]
        self.progressbar.set_fraction(1/4)
        results = DB.fetchone("select count(*) from result", (0,))[0]
        self.progressbar.set_fraction(2/4)
        keys, trigrams, words = DB.fetchall(
            "select count(*),sum(count) from statistic group by type order by type")
        self.progressbar.set_fraction(3/4)
        first = DB.fetchone("select w from result order by w asc limit 1", (time.time(), ))[0]
        self.progressbar.set_fraction(4/4)

        total = keys[0] + trigrams[0] + words[0]
        history = (time.time() - first) / 86400

        self.stats.set_text(f"""
Texts: {texts}
Results: {results}
Analysis data: {total} ({keys[0]} keys, {trigrams[0]} trigrams, {words[0]} words)
{keys[1]} characters and {words[1]} words typed in total.
First result was {round(history, 2)} days ago.
""")

        self.progressbar.set_fraction(0)

    def cleanup(self):
        s_in_day = 24*60*60
        now = time.time()
        pending = []

        for idx, grp, lim in [
                (1, 30, Settings.get("group_month")),
                (2, 7, Settings.get("group_week")),
                (3, 1, Settings.get("group_day")),
            ]:

            minimum = now - s_in_day * lim
            binsize = s_in_day * grp

            pending.extend(DB.fetchall(f"""
                select avg(w), data, type, agg_mean(time, count), sum(count), sum(mistakes),
                    agg_median(viscosity)
                from statistic where w <= {minimum}
                group by data, type, cast(w/{binsize} as int)"""))
            self.progressbar.set_fraction(idx/5)

        DB.executemany("""insert into statistic (w, data, type, time, count, mistakes, viscosity)
            values (?,?,?,?,?,?,?)""", pending)
        self.progressbar.set_fraction(4/5)
        # FIXME vacuum not supported
        # DB.execute("vacuum")
        self.progressbar.set_fraction(5/5)
        DB.commit()
        self.progressbar.set_fraction(0)

if __name__ == '__main__':
    GtkUtil.show_in_window(DatabaseWidget())
