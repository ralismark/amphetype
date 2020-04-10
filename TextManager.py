#!/usr/bin/env python3

import os.path as path
import time
import hashlib

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject

from Text import LessonMiner
from Data import DB
import GtkUtil
from Config import Settings, SettingsEdit, SettingsCombo

class SourceModel(Gtk.TreeStore):
    columns = {
        "ID": int,
        "Source": str,
        "Length": int,
        "Results": int,
        "WPM": float,
        "Disabled": str,
        }

    def __init__(self):
        Gtk.TreeStore.__init__(self)
        self.set_column_types(list(SourceModel.columns.values()))

        self.populate_data()

    def populate_data(self):
        self.clear()
        for source in DB.fetchall("""
            select s.rowid,s.name,t.count,r.count,r.wpm,ifelse(nullif(t.dis,t.count),'No','Yes')
                from source as s
                left join (select source,count(*) as count,count(disabled) as dis from text group by source) as t
                    on (s.rowid = t.source)
                left join (select source,count(*) as count,avg(wpm) as wpm from result group by source) as r
                    on (t.source = r.source)
                where s.disabled is null
                order by s.name"""):
            s_iter = self.append(None, list(source))
            for text in DB.fetchall("""
                select t.rowid,substr(t.text,0,40)||"...",length(t.text),r.count,r.m,ifelse(t.disabled,'Yes','No')
                from (select rowid,* from text where source = ?) as t
                left join (select text_id,count(*) as count,agg_median(wpm) as m from result group by text_id) as r
                    on (t.id = r.text_id)
                order by t.rowid""", (source[0], )):
                self.append(s_iter, list(text))

class TextManager(GtkUtil.AmphBoxLayout):
    __gsignals__ = {
        "refresh-sources": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "go-to-text": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "set-text": (GObject.SignalFlags.RUN_FIRST, None, (str, int, str)),
        }

    default_text = (
        "", 0,
        "Welcome to Amphetype!\n"
        "A typing program that not only measures"
        " your speed and progress, but also gives you"
        " detailed statistics about problem keys,"
        " words, common mistakes, and so on. This is"
        " just a default text since your database is"
        " empty. You might import a novel or text of"
        " your choosing and text excerpts will be"
        " generated for you automatically. There are"
        " also some facilities to generate lessons"
        " based on your past statistics! But for now,"
        " go to the 'Sources' tab and try adding some"
        " texts from the 'txt' directory.")

    def __init__(self):
        GtkUtil.AmphBoxLayout.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)

        self.diff_eval = lambda x: 1
        self.model = SourceModel()

        treeview = GtkUtil.AmphTreeView(self.model)
        self.tree = treeview.treeview
        self.tree.connect("row-activated", self.double_clicked)
        self.tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        self.progress = Gtk.ProgressBar()

        self.append_layout([
            [
                "Below you will see the different text sources used. Disabling"
                " texts or sources deactivates them so they won't be selected for"
                " typing. You can double click a text to do that particular text.\n",
                (treeview, ),
                self.progress,
                [GtkUtil.new_button("Import Texts", self.add_files),
                 GtkUtil.new_button("Enable All", self.enable_all),
                 GtkUtil.new_button("Delete Disabled", self.delete_disabled),
                 GtkUtil.new_button("Update List", self.update)],
                [GtkUtil.new_button("Toggle", self.toggle_selected),
                 " all selected text"],
            ], [
                ["Selection method for new lessons",
                 SettingsCombo('select_method', ['Random', 'In Order', 'Difficult', 'Easy'])],
                "(in order works by selecting the next text after the one you"
                " completed last, in the order they were added to the database,"
                " easy/difficult works by estimating your WPM for several random"
                " texts and choosing the fastest/slowest)\n",
                0,
                "Repeat texts that don't meet the following requirements",
                ["WPM:", SettingsEdit("min_wpm")],
                ["Accuracy:", SettingsEdit("min_acc")],
                "Repeat lessons that don't meet the following requiements",
                ["WPM:", SettingsEdit("min_lesson_wpm")],
                ["Accuracy:", SettingsEdit("min_lesson_acc")],
            ]])

        Settings.connect("change_select_method", lambda *_: self.set_select())
        self.set_select()

    def set_select(self):
        method = Settings.get("select_method")
        if method in (0, 1):
            self.diff_eval = lambda x: 1
            self.next_text()
            return

        hist = time.time() - 86400 * Settings.get("history")
        tri = dict(DB.execute("""
            select data,agg_median(time) as wpm from statistic
            where w >= ? and type = 1
            group by data""", (hist, )).fetchall())

        vals = list(tri.values())
        if not vals:
            self.diff_eval = lambda x: 1
            self.next_text()
            return
        vals.sort(reverse=True)
        expect = vals[len(vals) // 4]

        def func(target):
            text = target[2]
            # FIXME what does v do here?
            # v = 0
            total = 0.0
            for i in range(0, len(text)-2):
                trigram = text[i:i+3]
                if trigram in tri:
                    total += tri[trigram]
                else:
                    total += expect
                    # v += 1
            avg = total / (len(text)-2)
            return 12.0/avg
        self.diff_eval = func
        self.next_text()

    def add_files(self):
        filepicker = Gtk.FileChooserDialog()
        filepicker.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        filepicker.add_button(Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT)
        result = filepicker.run()
        fname = filepicker.get_filename()
        filepicker.destroy()
        if result == Gtk.ResponseType.CANCEL or fname is None:
            return

        lminer = LessonMiner(fname)
        lminer.connect("progress", lambda p: self.progress.set_fraction(p/100))
        self.add_texts(fname, lminer, update=False)
        self.progress.set_fraction(0)

        self.update()
        DB.commit()

    def update(self):
        self.emit("refresh-sources")
        self.model.populate_data()


    def add_texts(self, source, texts, lesson=None, update=True):
        idx = DB.get_source(source, lesson)
        out = []
        for text in texts:
            hasher = hashlib.sha1()
            hasher.update(text.encode("utf-8"))
            text_hash = hasher.hexdigest()
            dis = 1 if lesson == 2 else None
            try:
                DB.execute("insert into text (id,text,source,disabled) values (?,?,?,?)",
                           (text_hash, text, idx, dis))
                out.append(text_hash)
            except Exception:
                # TODO properly handle exception
                pass # silently skip ...
        if update:
            self.update()
        if lesson:
            DB.commit()
        return out

    def new_review(self, review):
        added = self.add_texts("<Reviews>", [review], lesson=2, update=False)
        if added:
            tgt = DB.fetchone("select id,source,text from text where id = ?",
                              self.default_text, added)
            self.emit("set-text", *tgt)
        else:
            self.next_text()

    def next_text(self):
        kind = Settings.get("select_method")
        if kind != 1:
            # Not in order
            targets = DB.execute(
                f"""select id,source,text from text where disabled is null
                order by random() limit {Settings.get("num_rand")}""").fetchall()
            if not targets:
                target = None
            elif kind == 2:
                target = min(targets, key=self.diff_eval)
            elif kind == 3:
                target = max(targets, key=self.diff_eval)
            else:
                target = targets[0] # random, just pick the first
        else:
            # Fetch in order
            prev = (0,)
            result = DB.fetchone("""select r.text_id
                from result as r left join source as s on (r.source = s.rowid)
                where (s.discount is null) or (s.discount = 1) order by r.w desc limit 1""", None)
            if result is not None:
                prev = DB.fetchone("select rowid from text where id = ?", prev, result)
            target = DB.fetchone("""select id,source,text from text
                where rowid > ? and disabled is null order by rowid asc limit 1""", None, prev)
        if target is None:
            target = self.default_text

        self.emit("set-text", *target)

    def enable_all(self):
        DB.execute('update text set disabled = null where disabled is not null')
        self.update()
        DB.commit()

    def delete_disabled(self):
        DB.execute('delete from text where disabled is not null')
        DB.execute("""
            delete from source where rowid in (
                select s.rowid from source as s
                    left join result as r on (s.rowid=r.source)
                    left join text as t on (t.source=s.rowid)
                group by s.rowid
                having count(r.rowid) = 0 and count(t.rowid) = 0
            )""")
        DB.execute("""
            update source set disabled = 1 where rowid in (
                select s.rowid from source as s
                    left join result as r on (s.rowid=r.source)
                    left join text as t on (t.source=s.rowid)
                group by s.rowid
                having count(r.rowid) > 0 and count(t.rowid) = 0
            )""")
        self.emit("refresh-sources")
        self.update()
        DB.commit()

    def toggle_selected(self):
        model, paths = self.tree.get_selection().get_selected_rows()
        for path in paths:
            if model.iter_depth(model.get_iter(path)) == 0:
                continue

            row = Gtk.TreeModelRow(model, path)
            DB.execute("update text set disabled = 1 where rowid=?", (row[0], ))
        self.update()
        DB.commit()

    def double_clicked(self, treeview, where, _column):
        model = treeview.get_model()
        if model.iter_depth(model.get_iter(where)) == 0:
            return

        row = Gtk.TreeModelRow(model, where)
        tgts = DB.fetchall("select id,source,text from text where rowid = ?", (row[0], ))

        cur = tgts[0] if tgts else self.default_text
        self.emit("set-text", *cur)
        self.emit("go-to-text")

if __name__ == '__main__':
    GtkUtil.show_in_window(TextManager())
