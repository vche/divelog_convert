from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
from divelog_convert.formater import (
    DiveLogbook,DiveLogEntry,
    DiveLogFormater,
    DiveUnitPressure,
    DiveUnitDistance,
    DiveViolation
)


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

    def _strval(self, value):
        return value if value else ""

    def _datetime(self, datetimeobj: datetime):
        return datetimeobj.strftime('%Y%m%d%H%M%S')
    
    def _build_fsh(self, dive: DiveLogEntry):
        return f"FSH|^~<>{{}}|{self.DLA_ID}^^|ZXU|{self._datetime(datetime.now())}|\n"

    def _build_zsh(self, dive: DiveLogEntry):
        return "ZRH|^~<>{{}}|{}|{}|{}|{}|{}|{}|{}|\n".format(
            self._strval(dive.equipment.pdc.type),
            self._strval(dive.equipment.pdc.sn),
            self.NMRI_DEPTH_UNIT[self._config.unit_distance],
            self.NMRI_ALTITUDE_UNIT[self._config.unit_distance],
            self._config.unit_temperature.value,
            self.NMRI_PRESSURE_UNIT[self._config.unit_pressure],
            self._config.unit_volume.value
        )

    def _build_zar(self, dive: DiveLogEntry):
        return "ZAR{}\n"

    def _build_zdh(self, dive: DiveLogEntry, sampling_period = None):
        return "ZDH|{}|{}|I|Q{}S|{}|{}||PO2|\n".format(
            dive.dive_num,
            dive.dive_num,
            sampling_period or dive.equipment.pdc.sampling_period,
            self._datetime(dive.stats.start_datetime),
            self._strval(dive.stats.airtemp),
        )

    def _build_zdp(self, dive: DiveLogEntry):
        dive_data = "ZDP{\n"
        for sample in dive.data:
            dive_data += "|{}|{}|{}||{}|{}||{}||{}|\n".format(
                sample.timestamp_s/60,
                int(sample.depth),
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

        return "ZDT|{}|{}|{}|{}|{}|{}|\n".format(
            dive.dive_num,
            dive.dive_num,
            dive.stats.maxdepth,
            self._datetime(dive.stats.end_datetime),
            self._strval(dive.stats.mintemp),
            pressure_drop
        )

    def read_dives(self, filename: Path) -> DiveLogbook:
        with self.open_func(filename, "r") as dive_file:
            self.log.info(f"Reading dives read from {filename}")
            raw_content = dive_file.read()
            content = raw_content.decode() if isinstance(raw_content, bytes) else raw_content
            # print(content)
        return None

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
        dl7_data += self._build_zsh(dives[0])
        dl7_data += self._build_zar(dives[0])
        for dive in dives:
            dl7_data += self._build_zdh(dive)
            dl7_data += self._build_zdp(dive)
            dl7_data += self._build_zdt(dive)
        return dl7_data


class DL7DiverlogDiveLogFormater(DL7DiveLogFormater):
    """DL7 format with Diverlog+ specific information..."""
    name = "diverlog"

    def write_dives(self, filename: Path, logbook: DiveLogbook, single_file:bool = True):
        # Diverlogs only support 1 dive per file
        return super().write_dives(filename, logbook, single_file =False)

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
        return super()._build_zdh(dive, sampling_period=30)
