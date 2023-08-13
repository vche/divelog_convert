import re
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
from divelog_convert.formater import (
    DiveAirMix,
    Diver,
    DiveComputer,
    DiveLogLocation,
    DiveLogData,
    DiveLogbook,
    DiveLogEntry,
    DiveLogFormater,
    DiveUnitPressure,
    DiveUnitDistance,
    DiveUnitTemperature,
    DiveUnitVolume,
    DiveViolation
)


def key_for_value(dict, value):
    for key in dict:
        if dict[key].lower() == value.lower():
            return key


class DL7Error(Exception):
    pass

class DL7DiveLogFormater(DiveLogFormater):
    ext = ".zxu"
    name = "dl7"

    DLA_ID = "ABC123"
    NMRI_PRESSURE_UNIT={
        DiveUnitPressure.BAR: "bar",
        DiveUnitPressure.PSI: "PSIA",
        None: "",
    }
    NMRI_ALTITUDE_UNIT={
        DiveUnitDistance.METER: "ThM",
        DiveUnitDistance.FEET: "ThFt",
    }
    NMRI_DEPTH_UNIT={
        DiveUnitDistance.FEET: "FSWG",
        DiveUnitDistance.METER: "MSWG",
    }

    # Separators
    SEP_FIELD = "|"
    SEP_COMP = "^"
    SEP_EXT_START = "{"
    SEP_EXT_END = "}"

    # Segments
    SEG_FSH = "FSH"
    SEG_ZRH = "ZRH"
    SEG_ZAR = "ZAR"
    SEG_ZDH = "ZDH"
    SEG_ZDP = "ZDP"
    SEG_ZDT = "ZDT"

    def _strval(self, value):
        return value if value else ""

    def _datetime(self, datetimeobj: datetime):
        return datetimeobj.strftime('%Y%m%d%H%M%S')

    def _to_datetime(self, datetimestr: str):
        return datetime.strptime(datetimestr, '%Y%m%d%H%M%S')

    def _build_fsh(self, dive: DiveLogEntry):
        return f"{self.SEG_FSH}|^~<>{{}}|{self.DLA_ID}^^|ZXU|{self._datetime(datetime.now())}|\n"

    def _build_zrh(self, dive: DiveLogEntry):
        return "{}|^~<>{{}}|{}|{}|{}|{}|{}|{}|{}|\n".format(
            self.SEG_ZRH,
            self._strval(dive.equipment.pdc.type),
            self._strval(dive.equipment.pdc.sn),
            self.NMRI_DEPTH_UNIT[self._config.unit_distance],
            self.NMRI_ALTITUDE_UNIT[self._config.unit_distance],
            self._config.unit_temperature.value,
            self.NMRI_PRESSURE_UNIT[self._config.unit_pressure],
            self._config.unit_volume.value
        )

    def _build_zar(self, dive: DiveLogEntry):
        return f"{self.SEG_ZAR}{{}}\n"

    def _build_zdh(self, dive: DiveLogEntry, sampling_period = None):
        return "{}|{}|{}|I|Q{}S|{}|{}||PO2|\n".format(
            self.SEG_ZDH,
            dive.dive_num,
            dive.dive_num,
            sampling_period or dive.equipment.pdc.sampling_period,
            self._datetime(dive.stats.start_datetime),
            self._strval(dive.stats.airtemp),
        )

    def _build_zdp(self, dive: DiveLogEntry):
        dive_data = f"{self.ZDP}{{\n"
        for sample in dive.data:
            dive_data += "|{}|{}|{}||{}|{}||{}||{}|\n".format(
                sample.timestamp_s/60,
                sample.depth,
                "1" if sample.airmix.is_air() else f"2.{sample.airmix.po2()}",
                # opt. Current PO2
                "T" if DiveViolation.ASCENT in sample.violations else "F",
                "T" if DiveViolation.DECO in sample.violations else "F",
                # opt. Current Ceiling
                self._strval(sample.temp),
                self._strval(sample.pressure)
            )
        dive_data += "ZDP}\n"
        return dive_data


    def _build_zdt(self, dive: DiveLogEntry):
        pressure_drop = ""
        if dive.stats.pressure_in and dive.stats.pressure_out:
            pressure_drop = dive.stats.pressure_in - dive.stats.pressure_out 

        return "{}|{}|{}|{}|{}|{}|{}|\n".format(
            self.SEG_ZDT,
            dive.dive_num,
            dive.dive_num,
            dive.stats.maxdepth,
            self._datetime(dive.stats.end_datetime),
            self._strval(dive.stats.mintemp),
            pressure_drop
        )

    def read_dives(self, filename: Path) -> DiveLogbook:
        with self.open_func(filename, "r") as dive_file:
            self.log.info(f"Reading dives from {filename}")
            raw_content = dive_file.read()
            content = raw_content.decode() if isinstance(raw_content, bytes) else raw_content
            try:
                logbook = self.parse_dive_log_file(content)
                # self.log.info(f"{len(logbook.dives)} dives read from {filename}, {errors} errors")
            except DL7Error as e:
              self.log.error(f"Error parsing gile {filename}: {e}")
            return logbook

    def write_dives(self, filename: Path, logbook: DiveLogbook, single_file:bool = True):
        # Make sur the destination file has the right suffix
        if filename.suffix != self.ext:
            filename = filename.with_suffix(self.ext)

        if single_file:
            self.write_dive_data(filename, logbook.dives)
        else:
            i = 1
            for dive in logbook.dives:
                self.write_dive_data(filename.with_stem(f"{filename.stem}_{i}"), [dive])
                i += 1

    def write_dive_data(self, filename: Path, dives: List[DiveLogEntry]):
        with open(filename, "w") as dive_file:
            self.log.info(f"Writing dive to {filename}")
            dl7_dive = self.build_dive_log_file(dives)
            dive_file.write(dl7_dive)

    def build_dive_log_file(self, dives: List[DiveLogEntry]):
        dl7_data = ""
        dl7_data += self._build_fsh(dives[0])
        dl7_data += self._build_zrh(dives[0])
        dl7_data += self._build_zar(dives[0])
        for dive in dives:
            dl7_data += self._build_zdh(dive)
            dl7_data += self._build_zdp(dive)
            dl7_data += self._build_zdt(dive)
        return dl7_data

    def _parse_zar_line(self, logbook: DiveLogbook, dive: DiveLogEntry, line: str):
        # This is application defined, not in standard
        pass

    def _parse_zdp_line(self, logbook: DiveLogbook, dive: DiveLogEntry, line: str):
        tokens = line.split(self.SEP_FIELD)

        # Extract gas mix from dive sample
        if tokens[3] == '1':
            airmix = logbook.add_airmix(DiveAirMix())
        else:
            airmix = None
            po2 = tokens[3].split('.')
            if len(po2) == 2:
                # Air
                if po2[0] == '1':
                    airmix = logbook.add_airmix(DiveAirMix())
                # Nitrox
                elif po2[0] == '2':
                    airmix = logbook.add_airmix(DiveAirMix(o2=int(po2[1])))
                # Heliox
                elif po2[0] == '3':
                    self.log.warning(f"Heliox air mix not supported: {tokens[3]}")
                elif po2[0] == '4':
                    airmix = logbook.add_airmix(DiveAirMix(o2=int(po2[1])), n2=0, h2=1 - int(po2[1]))
                elif po2[0] == '5':
                    self.log.warning(f"Heliox air mix not supported: {tokens[3]}")
                # Trimix
                elif po2[0] == '6' or po2[0] == '7' or po2[0] == '8' or po2[0] == '9':
                    self.log.warning(f"Trimux air mix not supported: {tokens[3]}")
                else:
                    self.log.warning(f"Invalid gas switch: {tokens[3]}")
            
            if airmix:
                self._last_airmix = airmix
            else:
                airmix = self._last_airmix

        # Create new data point
        sample = DiveLogData(
            timestamp_s = float(tokens[1])*60,
            depth = float(tokens[2]),
            violations = [],
            airmix = airmix,
        )

        if len(tokens) > 5:
            # Extract violations
            if tokens[5] == "T":
                sample.violations.append(DiveViolation.ASCENT)
            if tokens[6] == "T":
                sample.violations.append(DiveViolation.DECO)
            if len(tokens) > 8 and tokens[8]:
                dive.temp = float(tokens[8])

        dive.data.append(sample)

    def _parse_fsh(self, tokens: str):
        if tokens[3] != "ZXU":
            raise DL7Error("FSH header is not ZXU, other profiles unsupported")

    def _parse_zrh(self, logbook: DiveLogbook, dive: DiveLogEntry, tokens: str):
        dive.equipment.pdc.type = tokens[2]
        dive.equipment.pdc.sn = tokens[3]
        self._config.unit_distance = DiveUnitDistance(key_for_value(self.NMRI_DEPTH_UNIT, tokens[4]))
        self._config.unit_distance = DiveUnitDistance(key_for_value(self.NMRI_ALTITUDE_UNIT, tokens[5]))
        self._config.unit_temperature = DiveUnitTemperature(tokens[6])
        self._config.unit_pressure = DiveUnitPressure(key_for_value(self.NMRI_PRESSURE_UNIT, tokens[7]))
        self._config.unit_volume = DiveUnitVolume(tokens[8])

    def _parse_zdh(self, logbook: DiveLogbook, dive: DiveLogEntry, tokens: str):
        dive.dive_num = tokens[2]
        dive.equipment.pdc.sampling_period = tokens[4]
        dive.stats.start_datetime = self._to_datetime(tokens[5])
        dive.stats.airtemp = tokens[6]

    def _parse_zdt(self, logbook: DiveLogbook, dive: DiveLogEntry, tokens: str):
        dive.stats.maxdepth = tokens[3]
        dive.stats.end_datetime = self._to_datetime(tokens[4])
        dive.stats.mintemp = tokens[5]

    def parse_dive_log_file(self, content: str) -> DiveLogbook:
        logbook = DiveLogbook(config=self._config)
        dive = DiveLogEntry()
        segment_parser = None
        for line in content.splitlines():
            tokens = line.split(self.SEP_FIELD)
            if tokens[0] == self.SEG_FSH:
                self._parse_fsh(tokens)
            elif tokens[0] == self.SEG_ZRH:
                self._parse_zrh(logbook, dive, tokens)
            elif tokens[0] == self.SEG_ZDH:
                self._parse_zdh(logbook, dive, tokens)
            elif tokens[0] == self.SEG_ZDT:
                self._parse_zdt(logbook, dive, tokens)
            elif tokens[0] == self.SEG_ZDP+self.SEP_EXT_START+self.SEP_EXT_END:
                raise DL7Error("No dive data found (empty ZDP segment)")
            elif tokens[0] == self.SEG_ZDP+self.SEP_EXT_START:
                segment_parser = self._parse_zdp_line
            elif tokens[0] == self.SEG_ZDP+self.SEP_EXT_END:
                segment_parser = None
            elif tokens[0] == self.SEG_ZAR+self.SEP_EXT_START+self.SEP_EXT_END:
                # Empty zar
                pass
            elif tokens[0] == self.SEG_ZAR+self.SEP_EXT_START:
                segment_parser = self._parse_zar_line
            elif tokens[0] == self.SEP_EXT_END:
                segment_parser = None
            else:
                if segment_parser:
                    segment_parser(logbook, dive, line)
                else:
                    self.log.warning(f"Discarded line (unknown segment or out of block): {line}")

        logbook.add_dive(dive)
        return logbook


class DL7DiverlogDiveLogFormater(DL7DiveLogFormater):
    """DL7 format with Diverlog+ specific information..."""
    name = "diverlog"
    SAMPLING_PERIOD = 30  # Diverlog only supports 30

    re_duid = re.compile(r"<DUID>((?P<ctype>.*?)_)?((?P<csn>[0-9]*)_)?(?P<ddate>[0-9]*)_(?P<dnum>[0-9]*)</DUID>")
    re_diver = re.compile(
        r"<DIVER_NAME>(FIRSTNAME=\[(?P<first_name>.*)\]\s*,\s*)?LASTNAME=\[(?P<last_name>.*)\]<\/DIVER_NAME>"
    )
    re_pdc_model = re.compile(r"<PDC_MODEL>(?P<pdc_model>.*)</PDC_MODEL>")
    re_pdc_sn = re.compile(r"<PDC_SERIAL>(?P<pdc_serial>.*)</PDC_SERIAL>")
    re_pdc_mn = re.compile(r"<MANUFACTURER>(?P<pdc_manufacturer>.*)</MANUFACTURER>")
    re_pdc_fw = re.compile(r"<PDC_FIRMWARE>(?P<pdc_firmware>.*)</PDC_FIRMWARE>")
    re_rating = re.compile(r"<RATING>(?P<rating>.*)</RATING>")
    re_location = re.compile(
        r"<LOCATION>(DIVESITE=\[(?P<site>.*?)\])?,?(GPS=\[(?P<lat>[0-9,\.,\-]*),(?P<long>[0-9,\.,\-]*)\])?"
        r",?(LOCNAME=\[(?P<name>.*?)\])?,?(CITY=\[(?P<city>.*?)\])?(,STATE/PROVINCE=\[(?P<state>.*?)\])?"
        r",?(COUNTRY=\[(?P<country>.*?)\])?.*</LOCATION>"        
    )


    def write_dives(self, filename: Path, logbook: DiveLogbook, single_file:bool = True):
        # Diverlogs only support 1 dive per file
        return super().write_dives(filename, logbook, single_file =False)

    def _parse_zar_line(self, logbook: DiveLogbook, dive: DiveLogEntry, line: str):
        # Parse the dive uid
        duid = self.re_duid.search(line)
        if duid:
            duid_dict = duid.groupdict()
            dive.dive_num = duid_dict.get("dnum")

        # Parse diver info
        diver = self.re_diver.search(line)
        if diver:
            res = diver.groupdict()
            fn = res.get('first_name')
            ln = res.get('last_name')
            if not fn:
                tokens = ln.split('¶')
                if len(tokens) > 1:
                    fn = tokens[0]
                    ln = tokens[1]
            dive.diver = Diver(first_name=fn, last_name=ln)
            logbook.diver = dive.diver

        # Parse pdc info
        pdc_model = self.re_pdc_model.findall(line)
        if pdc_model:
            dive.equipment.pdc.type = pdc_model[0]
        pdc_sn = self.re_pdc_sn.findall(line)
        if pdc_sn:
            dive.equipment.pdc.sn = pdc_sn[0] 
        pdc_mn = self.re_pdc_mn.findall(line)
        if pdc_mn:
            dive.equipment.pdc.manufacturer = pdc_mn[0]
        # pdc_fw = self.re_pdc_fw.findall(line)
        # pdc_fw = pdc_fw[0] if pdc_fw else None

        # Parse location info
        loc = self.re_location.search(line)
        if loc:
            loc_dict = loc.groupdict()
            dive.location = DiveLogLocation(
                divesite = loc_dict.get("site"),
                gps = (loc_dict.get("lat"), loc_dict.get("long")),
                locname = loc_dict.get("name"),
                city = loc_dict.get("city"),
                state_province = loc_dict.get("state"),
                country = loc_dict.get("country"),
            )

        # Parse rating
        res = self.re_rating.search(line)
        if res:
            dive.rating = int(res["rating"])

    def _build_zar(self, dive: DiveLogEntry):
        zar_data = "ZAR{\n<AQUALUNG>\n<APP>DiverLog+</APP>\n"
        zar_data += "<DUID>{}{}{}{}{}_{}</DUID>\n".format(
            self._strval(dive.equipment.pdc.type),
            "_" if dive.equipment.pdc.type else "",
            self._strval(dive.equipment.pdc.sn),
            "_" if dive.equipment.pdc.sn else "",
            self._datetime(datetime.now()),
            dive.dive_num
        )
        zar_data += "<TITLE> </TITLE>\n"
        zar_data += f"<DIVE_DT>{self._datetime(dive.stats.start_datetime)}</DIVE_DT>\n"
        zar_data += f"<FILE_DT>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</FILE_DT>\n"
        zar_data += "<DIVE_MODE>0</DIVE_MODE>\n"
        zar_data += f"<PDC_MODEL>{self._strval(dive.equipment.pdc.type)}</PDC_MODEL>\n"
        zar_data += f"<PDC_SERIAL>{self._strval(dive.equipment.pdc.sn)}</PDC_SERIAL>\n"
        zar_data += f"<MANUFACTURER>{dive.equipment.pdc.manufacturer}</MANUFACTURER>\n"
        zar_data += f"<PDC_FIRMWARE>{dive.equipment.pdc.firmware}</PDC_FIRMWARE>\n"
        zar_data += f"<DIVER_NAME>LASTNAME=[{dive.diver.strid()}]</DIVER_NAME>\n"
        lat,long = dive.location.gps
        zar_data += "<LOCATION>DIVESITE=[{}],GPS=[{},{}],LOCNAME=[{}],CITY=[{}],STATE/PROVINCE=[{}],".format(
            self._strval(dive.location.divesite),
            self._strval(lat),
            self._strval(long),
            self._strval(dive.location.divesite),
            self._strval(dive.location.city),
            self._strval(dive.location.state_province)
        )
        zar_data += "COUNTRY=[{}],AIRTEMP={},SURFACETEMP={},MINTEMP={}</LOCATION>\n".format(
            self._strval(dive.location.country),
            self._strval(dive.stats.airtemp),
            self._strval(dive.stats.surfacetemp),
            self._strval(dive.stats.mintemp)
        )
        # <GEAR>GEAR_UNITS=0</GEAR>\n
        zar_data += "<RATING>{}</RATING>\n".format(dive.rating)
        hours, minutes, seconds = dive.stats.duration_hms()
        zar_data += "<DIVESTATS>DIVENO={},DATATYPE=8,DECO=N,VIOL={},MODE=0,MANUALDIVE=0,EDT={},".format(
            dive.dive_num,
            "N" if len(dive.stats.violations) == 0 else "Y",
            f"{hours}{minutes}{seconds}",
        )
        zar_data += "SI=000000,MAXDEPTH={},MAXO2=0,PO2={},MINTEMP={}</DIVESTATS>\n".format(
            dive.stats.maxdepth,
            dive.equipment.airmixes[0].po2(),
            dive.stats.mintemp,
        )
        i = 1
        for tank in dive.equipment.tanks:
            if tank:
                zar_data += "<TANK>NUMBER={},TID=0,ON=Y,CYLNAME=[{}],CYLSIZE={}{},WORKINGPRESSURE=3000PSI,".format(
                    i,
                    tank.name,
                    tank.volume,
                    self._config.unit_volume.value,
                )
                zar_data += "STARTPRESSURE={},ENDPRESSURE={},FO2=0,AVGDEPTH={},DIVETIME={},SAC=0</TANK>\n".format(
                    dive.stats.pressure_in,
                    dive.stats.pressure_out,
                    dive.stats.avgdepth,
                    dive.stats.duration_min()
                )
            i = i + 1

        zar_data += "</AQUALUNG>\n}\n"
        return zar_data

    def _build_zdh(self, dive: DiveLogEntry):
        # Force the sampling rate to 30s as diverlog doesn't support any other value -_-"
        return super()._build_zdh(dive, sampling_period=self.SAMPLING_PERIOD)
