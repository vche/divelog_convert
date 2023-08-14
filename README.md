## divelog_convert

Utility tool to convert various dive log formats.
Currently support 
- DL7 from [divecloud](https://www.divecloud.net/)/[diverlog+](https://www.ediverlog.com/)
- CSV from [diviac](https://logbook.diviac.com/)
- UDDF support for [jtrak/smarttrak](https://ww2.scubapro.com/en-GB/HKG/product-support.aspx?subject=manuals)/[subsurface](https://subsurface-divelog.org/)/[macdive](https://www.mac-dive.com/)/[diviac](https://logbook.diviac.com/)).
- Mac native ui (currently only in command line)
- Actual documentation with examples

## development

After git clone:

### Installing locally

```
pip install .
```

### Installing for development

```
virtualenv pyvenv
source pyvenv bin/activate
python setup.py develop
```

Building osx bundle (requires pyinstaller installed):
```
pyinstaller -y divelog_convert.spec
```

TODO: generate universal installer

Build installer

https://www.recitalsoftware.com/blogs/148-howto-build-a-dmg-file-from-the-command-line-on-mac-os-x
https://gist.github.com/jadeatucker/5382343


## TODO
- check if it's worth getting gps locs (macdive and/or subsurface) ? probably not...
- add config to an optional file (now hardcoded, ewwww)
- handle xml subsurface ?
- handle macdive xml ?

- Process to get all dives from differnt sources into a new app:
    - From Diviac:
        - Diviac export to csv
        - Convert csv to uddf: `divelog_convert -d -i test/data/diviac-export3.csv -if diviac -o temp/from_diviac.uddf`
    - From JTrak:
        - Export to uddf
        - Enrich: `divelog_convert -d -i test/data/jtrak-export.uddf -o temp/from_jtrak.uddf`
    - From dive cloud:
        - Export diverlog cloud [to be synced from dive computer to get latest dives]
        - Convert required zxu to uddf: `divelog_convert -d -i data/divecloud_20221226174016.zip -if diverlog -o temp/from_divelog.uddf`
    - Import all uddf to subsurface / macdive
        - Merge all uddf into one: `divelog_convert -d -i temp/from_diviac.uddf,temp/from_divelog.uddf -o temp/all_dives.uddf`

- Process to import dives to diverlog
    - Diviac export to csv (or macdive/subsurface)
    - Export to zxu `divelog_convert -d -i test/data/diviac-export3.csv -o temp/aqualung -of "diverlog"`
    - Import all .zxu to diverlog cloud
    - Sync with app

TODO:
    - Support heliox and trimix in dl7 air parse (parse_zdp_line)
    - Import missing dives from smartz
    - Fix UI
