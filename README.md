## divelog_convert

Utility tool to convert various dive log formats.
Currently support 
- DL7 from [divecloud](https://www.divecloud.net/)/[diverlog+](https://www.ediverlog.com/)
- CSV from [diviac](https://logbook.diviac.com/)

Work in progress:
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

- Process to get all into a new app:
    - Diviac export to csv
    - Convert csv to uddf: `divelog_convert -d -i test/data/diviac-export3.csv -if diviac -o temp/diviac_convert.uddf`

    - Export diverlog cloud [to be synced from dive computer to get latest dives]
    - TODO: support .zip : unzip, get and import all zxu, remove
    - TODO: Convert required zxu to uddf: `divelog_convert -d -i test/data/diviac-export3.csv -if diviac -o temp/diviac_convert.uddf`

    - Import all uddf to subsurface / macdive

- Process to import dives to diverlog
    - Diviac export to csv (or macdive/subsurface)
    - Export to zxu `divelog_convert -d -i test/data/diviac-export3.csv -o temp/aqualung -of "diverlog"`
    - Import all .zxu to diverlog cloud
    - Sync with app
