import xmltodict
from dicttoxml import dicttoxml
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
from datetime import datetime, timedelta

from divelog_convert.formater import (
    Diver,
    DiveAirMix,
    DiveComputer,
    DiveEquipment,
    DiveLogbook,
    DiveLogLocation,
    DiveLogData,
    DiveLogStats,
    DiveLogEntry,
    DiveLogFormater,
    DiveTank,
    DiveViolation
)


class XmlDiveLogFormater(DiveLogFormater):

    def read_dives(self, filename: Path) -> DiveLogbook:
        with open(filename, "r") as dive_file:
            self.log.info(f"Reading dives read from {filename}")
            dive_dict = xmltodict.parse(dive_file.read())
            logbook = self.parse_xml_dict(dive_dict)
            errors = 0
            self.log.info(f"{len(logbook.dives)} dives read from {filename}, {errors} errors")
            return logbook

    def write_dives(self, filename: Path, logbook: DiveLogbook):
        if filename.suffix != self.ext:
            filename = filename.with_suffix(self.ext)

        with open(filename, "w") as dive_file:
            self.log.info(f"Writing {len(logbook.dives)} dives written to {filename}")
            dive_dict = self.build_xml_dict(logbook)
            xml_data = dicttoxml(dive_dict)
            dive_file.write(xml_data)

    @abstractmethod
    def parse_xml_dict(self, xml_dict: Dict[str, Any]) -> List[DiveLogEntry]:
        ...

    @abstractmethod
    def build_xml_dict(self, entry: DiveLogEntry) -> Dict[str, Any]:
        ...


class UddfDiveLogFormater(XmlDiveLogFormater):
    @property
    def ext(self):
        return ".uddf"

    @property
    def name(self):
        return "uddf"


    @property
    def name(self):
        return "diviac"

    def __init__(self, config=None):
        super().__init__(config)
    

    def parse_xml_dict(self, xml_dict: Dict[str, Any]) -> DiveLogbook:
        # print(f"pipo input {xml_dict}")
        print("prout")
        print(xml_dict['uddf'].keys())
        print(xml_dict['uddf']['diver'].keys())
        for b in xml_dict['uddf']['diver']['buddy']:
            print(b['personal']['firstname'])
        return DiveLogbook()

    def build_xml_dict(self, logbook: DiveLogbook) -> Dict[str, Any]:
        return {}
