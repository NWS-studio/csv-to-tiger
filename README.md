# csv-to-tiger

Convert a cutlist CSV into a TigerStop `.tiger` file.

**→ [nws-studio.github.io/csv-to-tiger](https://nws-studio.github.io/csv-to-tiger)**

Drop a CSV, mark which column holds tube length, drag columns to set how they read
on the controller, save. Runs entirely in the browser — nothing is uploaded, and it
works offline once the page has loaded.

Replaces the TigerLink6 + `CutListLinks.xml` import path, which required the CSV's
column count and length-column position to be declared in advance on the machine
and failed silently when they didn't match.

## Features

- Length column matched by header name, confirmed by hand — never guessed from values
- Any other numeric column sitting inside the machine's range is flagged, so
  ambiguity is visible rather than silently resolved
- Up to 5 display fields, dragged into the order they appear on the controller
- Split one CSV into several `.tiger` files by the value of any column
- Refuses to write on ragged rows, non-numeric lengths, or lengths outside
  153–2438 mm, naming the offending row numbers

## Command line

For same-folder output and scripting:

```
python3 csv2tiger.py cutlist.csv
python3 csv2tiger.py cutlist.csv --length Length --labels "Tube #,Radius" --name EARTH-01
```

`--length` and `--labels` accept header names or 1-based column indices, so
headerless CSVs work: `--length 4 --labels 1,3`

## The .tiger format

Plain XML. No serial number, no checksum, no machine binding, no work-order number
inside the file. TigerTouch loads `.tiger` files by arbitrary filename — the
`00_name_10000187` convention is only how TigerLink6 named its own output.

```xml
<CutList>
  <style>Setpoint</style>  <unit>Metric</unit>
  <headCut>0</headCut>     <tailCut>0</tailCut>
  <printStrings>
    <LabelField><header>Tube #:</header><column>0</column>…</LabelField>
  </printStrings>
  <pieces>
    <Piece>
      <labelStrings><string>258</string><string>9999999</string></labelStrings>
      <length>457.01</length>  <quantity>1</quantity>
      <angle1>0</angle1>       <angle2>0</angle2>
    </Piece>
```

Element order is load-bearing — TigerTouch reads a fixed sequence. `printStrings`
order sets display order and is independent of source column order; `labelStrings`
must follow the same order.

Files saved *by* TigerTouch carry extra runtime fields (`waste`, `yield`,
`remnant`, `timesLoaded`, per-piece `completed`). Those are written by the machine
and aren't required on input.

## Verification

Both implementations were checked against real TigerLink6 output. `examples/`
holds a source CSV and the `.tiger` TigerLink6 produced from it:

```
python3 csv2tiger.py "examples/Test swatch surface B 01_05 - Sheet1.csv" \
  --labels "Tube #,Radius"
diff "examples/reference-tigerlink6-output.tiger" \
     "examples/Test swatch surface B 01_05 - Sheet1.tiger"
```

Identical apart from one display label — the reference used `Tube #:` with a colon,
from the old XML profile. Header constants, element order, CRLF line endings and
absence of a BOM all match.

## Machine notes

Defaults target a TigerStop TS08 with no miter positioner. Adjust for yours.

- **153 mm** effective minimum position. Below it the controller silently refuses
  to move (TigerStop support, Oct 2024).
- **2438 mm** range (96").
- Filenames over **18 characters** truncate on the controller.
- If you still use TigerLink6 for anything, `%APPDATA%\TigerLink6\csvoutput.txt`
  must be `FALSE` — set `TRUE` it emits `.csv` instead of `.tiger`, silently.
  `autoconnect.txt` must be `FALSE` or TigerLink6 takes the serial connection
  away from TigerTouch.
