#!/usr/bin/env python3

tag = False
def distance(*args):
    global tag
    if not tag:
        import GtkUtil
        GtkUtil.show_dialog("Missing Module", "The py-editdist module is missing!")
        tag = True
    return 0.01
