# Amphetype Fork

This is a fork of amphetype that overhauls pretty much the entire code:

1. Converting it to full python3
2. Switching out PyQt for Gtk

This rewrite is basically feature complete compared to the original.

# Running

This depends on:

- `python-gobject`
- optionally, `py-editdist` (For fetching words from a wordfile that are "similar" to your target words in the lesson generator.)

To run, type:

```
./Amphetype.py
```
