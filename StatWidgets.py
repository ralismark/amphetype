#!/usr/bin/env python3
import time

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from Data import DB
import GtkUtil
import Text
from Config import Settings, SettingsCombo, SettingsEdit

class WordModel(GtkUtil.AmphModel):
    columns = {
        "Item": str,
        "Speed (wpm)": float,
        "Accuracy (%)": float,
        "Viscosity": float,
        "Count": int,
        "Mistakes": int,
        "Impact": float,
        }

class StringStats(GtkUtil.AmphBoxLayout):
    def __init__(self):
        GtkUtil.AmphBoxLayout.__init__(self)
        self.model = WordModel()
        treeview = GtkUtil.AmphTreeView(self.model)

        self.update()

        which = SettingsCombo('ana_which', [
            ('wpm asc', 'slowest'),
            ('wpm desc', 'fastest'),
            ('viscosity desc', 'least fluid'),
            ('viscosity asc', 'most fluid'),
            ('accuracy asc', 'least accurate'),
            ('misses desc', 'most mistyped'),
            ('total desc', 'most common'),
            ('damage desc', 'most damaging'),
            ])

        what = SettingsCombo('ana_what', ['keys', 'trigrams', 'words'])
        lim = SettingsEdit('ana_many')
        mincount = SettingsEdit('ana_count')

        # XXX why are sometimes no args provided, sometimes Config.Settings?
        Settings.connect("change_ana_which", lambda *_: self.update())
        Settings.connect("change_ana_what", lambda *_: self.update())
        Settings.connect("change_ana_many", lambda *_: self.update())
        Settings.connect("change_ana_count", lambda *_: self.update())

        # TODO send lessons to generator
        send_to_generator = lambda: None

        self.append_layout([
            ["Display statistics about the", which, what, None,
             GtkUtil.new_button("Update list", self.update),
             GtkUtil.new_button("Send list to Lesson Generator", send_to_generator)],
            ["Limit list to", lim, "items and don't show items with a count less than", mincount],
            (treeview, ),
            ])

    def update(self):
        which = Settings.get("ana_which")
        what = Settings.get("ana_what")
        limit = Settings.get("ana_many")
        least = Settings.get("ana_count")
        hist = time.time() - Settings.get("history") * 86400.0

        sql = f"""select data,12.0/time as wpm,
            100.0-100.0*misses/cast(total as real) as accuracy,
            viscosity,total,misses,
            total*time*time*(1.0+misses/total) as damage
                from
                    (select data,agg_median(time) as time,agg_median(viscosity) as viscosity,
                    sum(count) as total,sum(mistakes) as misses
                    from statistic where w >= ? and type = ? group by data)
                where total >= ?
                order by {which} limit {limit}"""

        self.model.set_stats(DB.fetchall(sql, (hist, what, least)))

if __name__ == '__main__':
    GtkUtil.show_in_window(StringStats())
