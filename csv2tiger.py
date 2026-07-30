#!/usr/bin/env python3
"""
csv2tiger.py - Convert a cutlist CSV directly to a TigerStop .tiger file.

Bypasses TigerLink6 and CutListLinks.xml entirely. Reads any CSV, writes a
.tiger that TigerTouch loads directly.

Usage:
    python3 csv2tiger.py cutlist.csv
    python3 csv2tiger.py cutlist.csv --length Length --labels "Tube #,Radius"
    python3 csv2tiger.py cutlist.csv --out "D:/cutlists/"

Defaults find a column named "Length" and label with "Tube #" and "Radius"
if present. Everything is validated before anything is written.
"""

import argparse
import csv
import os
import sys
from xml.sax.saxutils import escape

# Machine limits for a TigerStop TS08 with no miter positioner.
# 153mm is the effective hard minimum: below it the controller silently
# refuses to move. 2438mm is the TS08's 96in range. Adjust for your machine.
MIN_LENGTH_MM = 153.0
MAX_LENGTH_MM = 2438.0  # TS08 96" range

# Fixed header values, taken from pristine TigerLink6 output. Verified
# identical across every .tiger TigerLink6 generated on our machine.
DEFAULTS = {
    "style": "Setpoint",
    "unit": "Metric",
    "isOptimized": "false",
    "headCut": "0",
    "tailCut": "0",
    "patternStockLength": "0",
    "repeatCount": "0",
    "sequenceNumber": "1",
    "sendFileName": "true",
    "quantityMultiples": "false",
    "isInfinite": "false",
    "isCascade": "false",
}

# Label positions on the controller readout. Second label sits 24px below.
LABEL_Y = [0, 24, 48, 72]


def die(msg):
    sys.stderr.write("ERROR: %s\n" % msg)
    sys.exit(1)


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.reader(fh)]
    if not rows:
        die("%s is empty" % path)
    header = [c.strip() for c in rows[0]]
    data = [r for r in rows[1:] if any(c.strip() for c in r)]
    if not data:
        die("%s has a header but no data rows" % path)
    widths = set(len(r) for r in data)
    if len(widths) > 1:
        die("ragged CSV - data rows have %s different field counts: %s"
            % (len(widths), sorted(widths)))
    if widths and list(widths)[0] != len(header):
        die("header has %d columns but data rows have %d"
            % (len(header), list(widths)[0]))
    return header, data


def resolve(header, name, what):
    """Resolve a column by name (case-insensitive) or 1-based index."""
    if name.isdigit():
        idx = int(name) - 1
        if not 0 <= idx < len(header):
            die("%s column %s is out of range (CSV has %d columns)"
                % (what, name, len(header)))
        return idx
    low = [h.lower() for h in header]
    if name.lower() in low:
        return low.index(name.lower())
    die("%s column %r not found. CSV headers are: %s"
        % (what, name, ", ".join(header)))


def build(fname, lengths, label_headers, label_cols, label_values):
    out = []
    w = out.append
    w('<?xml version="1.0" encoding="utf-8"?>')
    w('<CutList xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
      'xmlns:xsd="http://www.w3.org/2001/XMLSchema">')
    # Element order matters - .NET XmlSerializer reads these as a sequence.
    for tag in ("style", "unit", "isOptimized", "headCut", "tailCut",
                "patternStockLength", "repeatCount", "sequenceNumber"):
        w("  <%s>%s</%s>" % (tag, DEFAULTS[tag], tag))
    w("  <sortString />")
    w("  <sendFileName>%s</sendFileName>" % DEFAULTS["sendFileName"])
    w("  <fname>%s</fname>" % escape(fname))
    for tag in ("quantityMultiples", "isInfinite", "isCascade"):
        w("  <%s>%s</%s>" % (tag, DEFAULTS[tag], tag))

    w("  <printStrings>")
    for n, hdr in enumerate(label_headers):
        w("    <LabelField>")
        w("      <header>%s</header>" % escape(hdr))
        w("      <fontSize>12</fontSize>")
        w("      <x>0</x>")
        w("      <y>%d</y>" % LABEL_Y[n % len(LABEL_Y)])
        w("      <column>%d</column>" % label_cols[n])  # zero-based
        w("    </LabelField>")
    w("  </printStrings>")

    w("  <pieces>")
    for i, length in enumerate(lengths):
        w("    <Piece>")
        w("      <labelStrings>")
        for vals in label_values:
            w("        <string>%s</string>" % escape(vals[i]))
        w("      </labelStrings>")
        w("      <length>%s</length>" % length)
        w("      <quantity>1</quantity>")
        w("      <angle1>0</angle1>")
        w("      <angle2>0</angle2>")
        w("    </Piece>")
    w("  </pieces>")
    w("</CutList>")
    return "\r\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv_path")
    p.add_argument("--length", default="Length",
                   help="length column: header name or 1-based index")
    p.add_argument("--labels", default="Tube #,Radius",
                   help="comma-separated label columns (names or indices)")
    p.add_argument("--out", default=None,
                   help="output directory (default: alongside the CSV)")
    p.add_argument("--name", default=None,
                   help="cutlist name (default: CSV filename without extension)")
    p.add_argument("--no-limit-check", action="store_true",
                   help="skip the %g-%gmm range check" % (MIN_LENGTH_MM, MAX_LENGTH_MM))
    args = p.parse_args()

    if not os.path.isfile(args.csv_path):
        die("no such file: %s" % args.csv_path)

    header, data = read_csv(args.csv_path)
    li = resolve(header, args.length, "length")

    label_names = [s.strip() for s in args.labels.split(",") if s.strip()]
    label_cols, label_headers = [], []
    for nm in label_names:
        try:
            label_cols.append(resolve(header, nm, "label"))
            label_headers.append(nm if nm.isdigit() else header[label_cols[-1]])
        except SystemExit:
            sys.stderr.write("  note: skipping label column %r (not in CSV)\n" % nm)
    label_values = [[r[c].strip() for r in data] for c in label_cols]

    lengths, problems = [], []
    for n, row in enumerate(data, start=2):
        raw = row[li].strip()
        try:
            v = float(raw)
        except ValueError:
            problems.append("row %d: length %r is not a number" % (n, raw))
            continue
        if not args.no_limit_check and not (MIN_LENGTH_MM <= v <= MAX_LENGTH_MM):
            problems.append("row %d: length %g is outside %g-%gmm"
                            % (n, v, MIN_LENGTH_MM, MAX_LENGTH_MM))
        # Preserve the CSV's own formatting - TigerLink does the same.
        lengths.append(raw)

    if problems:
        sys.stderr.write("Refusing to write. %d problem(s):\n" % len(problems))
        for msg in problems[:20]:
            sys.stderr.write("  %s\n" % msg)
        if len(problems) > 20:
            sys.stderr.write("  ... and %d more\n" % (len(problems) - 20))
        sys.exit(1)

    name = args.name or os.path.splitext(os.path.basename(args.csv_path))[0]
    outdir = args.out or os.path.dirname(os.path.abspath(args.csv_path))
    outpath = os.path.join(outdir, name + ".tiger")

    xml = build(name, lengths, label_headers, label_cols, label_values)
    with open(outpath, "w", encoding="utf-8", newline="") as fh:
        fh.write(xml)

    fl = [float(x) for x in lengths]
    print("wrote %s" % outpath)
    print("  %d pieces, %.2f-%.2fmm, total %.1fmm"
          % (len(lengths), min(fl), max(fl), sum(fl)))
    print("  length column: %d (%r)" % (li + 1, header[li]))
    print("  labels: %s" % (", ".join(
        "%r=col %d" % (h, c + 1) for h, c in zip(label_headers, label_cols))
        or "none"))
    if len(name) > 18:
        print("  note: name is %d chars - over 18 may truncate on the controller"
              % len(name))


if __name__ == "__main__":
    main()
