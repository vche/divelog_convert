import attr
import logging
import unicodedata
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum
from tempfile import TemporaryDirectory


class DiveViolation(Enum):
    ASCENT="Ascent rate violation"
    DECO="Decompression violation"
    SURFACE="Surface violation"
    ERROR="Generic Error"


class DiveUnitDistance(Enum):
    METER="m"
    FEET="ft"


class DiveUnitTemperature(Enum):
    CELSIUS="C"
    FAHRENHEIT="F"
    KELVIN="K"

    def from_unit(self, from_unit, value:float):
        return DiveUnitTemperature.convert_temperature_unit(from_unit, self, value)

    def to_unit(self, to_unit, value:float):
        return DiveUnitTemperature.convert_temperature_unit(self, to_unit, value)

    def convert_temperature_unit(from_unit, to_unit, value):
        if value is None:
            return 0
        if from_unit == DiveUnitTemperature.CELSIUS:
            if to_unit == DiveUnitTemperature.FAHRENHEIT:
                # (0°C × 9/5) + 32 = 32°F
                return float(value) * (9/5) + 32
            elif to_unit == DiveUnitTemperature.KELVIN:
                # 0°C + 273.15 = 273.15K
                return float(value) + 273.15
        elif from_unit == DiveUnitTemperature.FAHRENHEIT:
            if to_unit == DiveUnitTemperature.CELSIUS:
                # (0°F − 32) × 5/9 = -17.78°C
                return (float(value) - 32) * (5/9)

            elif to_unit == DiveUnitTemperature.KELVIN:
                # (0°F − 32) × 5/9 + 273.15 = 255.372K
                return (float(value) - 32) * (5/9) + 273.15

        elif from_unit == DiveUnitTemperature.KELVIN:
            if to_unit == DiveUnitTemperature.CELSIUS:
                # 0K − 273.15 = -273.1°C
                return float(value) - 273.15
            elif to_unit == DiveUnitTemperature.FAHRENHEIT:
                # (0K − 273.15) × 9/5 + 32 = -459.7°F
                return (float(value) - 273.15) * (9/5) + 32
        return value


class DiveUnitPressure(Enum):
    BAR="bar"
    PSI="psi"


class DiveUnitVolume(Enum):
    LITER="L"
    CUBICFEET="CF"


class DiveLogItem:
    def uuid(self):
        # We want to remove all special characther to keep unicode uuids
        if self.strid():
            uuid = unicodedata.normalize('NFKD',self.strid()).encode('ascii', 'ignore').decode()
            return f"{self.__class__.__name__}-{uuid}".replace(" ","_").lower()
        return None

    def strid(self):
        return ""

@attr.s
class DiveLogConfig:
    # TODO load defaults from config file: class_method from_yaml / from_json
    app_version = attr.ib(default="0.0.0", type=str)
    diver_first_name = attr.ib(default="Vivien", type=str)
    diver_last_name = attr.ib(default="Chene", type=str)
    unit_distance = attr.ib(default=DiveUnitDistance.METER, type=DiveUnitDistance)
    unit_temperature = attr.ib(default=DiveUnitTemperature.CELSIUS, type=DiveUnitTemperature)
    unit_pressure = attr.ib(default=DiveUnitPressure.BAR, type=DiveUnitPressure)
    unit_volume = attr.ib(default=DiveUnitVolume.LITER, type=DiveUnitVolume)
    pdc_manufacturer = attr.ib(default="Uwatec", type = str)
    pdc_type = attr.ib(default="SmartZ", type=str)
    pdc_sn = attr.ib(default="123456", type=str)
 
    diviac_date_format_ddmmyy = attr.ib(default=True, type=bool)
    diviac_time_format_24 = attr.ib(default=True, type=bool)

    def get_diviac_date_format(self):
        return "%d-%m-%Y" if self.diviac_date_format_ddmmyy else "%m-%d-%Y"

    def get_diviac_time_format(self):
        return "%H:%M" if self.diviac_time_format_24 else "%I:%M%p"

    def get_diviac_date_time_format(self):
        date_fmt = "%d-%m-%Y" if self.diviac_date_format_ddmmyy else "%m-%d-%Y"
        time_fmt = "%H:%M" if self.diviac_time_format_24 else "%I:%M%p"
        return f"{self.get_diviac_date_format()} {self.get_diviac_time_format()}"

@attr.s
class DiveLogLocation(DiveLogItem):
    divesite = attr.ib(default=None, type=str)
    gps = attr.ib(default=None, type = tuple[float, float])
    locname = attr.ib(default=None, type=str)
    city = attr.ib(default=None, type=str)
    state_province = attr.ib(default=None, type=str)
    street = attr.ib(default=None, type=str)
    country = attr.ib(default=None, type=str)
    notes = attr.ib(default="", type=str)
    rating = attr.ib(default=0, type=int)

    def __attrs_post_init__(self):
        if not self.divesite and self.locname:
            self.divesite = self.locname

    def strid(self):
        return self.divesite

@attr.s
class Diver(DiveLogItem):
    first_name = attr.ib(type = str)
    last_name = attr.ib(default = "", type = str)

    @classmethod
    def from_full_name(cls, full_name: str):
        tokens = full_name.split(" ")
        return cls(first_name=tokens[0], last_name=" ".join(tokens[1:]))

    def strid(self):
        return f"{self.first_name} {self.last_name}" if self.first_name and self.last_name else ""


@attr.s
class DiveSuit(DiveLogItem):
    name = attr.ib(type = str)
    type = attr.ib(default = None, type = str)

    def strid(self):
        return self.name


@attr.s
class DiveAirMix(DiveLogItem):
    name = attr.ib(default = None, type = str)
    o2 = attr.ib(default = 0.21, type = float)
    n2 = attr.ib(default = 0.79, type = float)
    he = attr.ib(default = 0.0, type = float)
    ar = attr.ib(default = 0.0, type = float)
    h2 = attr.ib(default = 0.0, type = float)

    def is_air(self) -> bool:
        return abs(0.21 - self.o2 ) < 0.001

    def po2(self):
        return int(self.o2 * 100)

    def __attrs_post_init__(self):
        # If only o2 is specified, fill n2
        if not self.n2:
            mix = self.h2 + self.ar + self.he
            self.n2 = 1 - (self.o2 + mix)
        # If no name is specified, build one, either "air" or based on o2 level
        if not self.name:
            if self.is_air():
                self.name = "air"
            else:
                self.name = "o2-{int(self.02*100)}"
        

    def strid(self):
        return self.name


@attr.s
class DiveTank(DiveLogItem):
    name = attr.ib(type = str)
    volume = attr.ib(default = 0, type = int)

    def strid(self):
        return f"{self.name} {self.volume}" if self.name and self.volume else ""


@attr.s
class DiveComputer(DiveLogItem):
    manufacturer = attr.ib(default="", type = str)
    firmware = attr.ib(default="", type = str)
    type = attr.ib(default=None, type=str)
    sn = attr.ib(default=None, type=str)
    sampling_period = attr.ib(default=1, type=int)

    def strid(self):
        return f"{self.type} {self.sn}" if self.type and self.sn else ""


@attr.s
class DiveLogStats:
    start_datetime = attr.ib(default=None, type=datetime)
    end_datetime = attr.ib(default=None, type=datetime)
    maxdepth = attr.ib(default=0.0, type = float)
    avgdepth = attr.ib(default=0.0, type = float)
    maxo2 = attr.ib(default=0.0, type = float)
    po2 = attr.ib(default=0.0, type = float)
    mintemp = attr.ib(default=0.0, type = float)
    pressure_in = attr.ib(default=0.0, type = float)
    pressure_out = attr.ib(default=0.0, type = float)
    violations = attr.ib(factory=list, type=list[DiveViolation])
    airtemp = attr.ib(default=0.0, type = float)
    surfacetemp = attr.ib(default=0.0, type = float)
    visibility = attr.ib(default=0.0, type = float)

    @property
    def duration(self) -> timedelta:
        return self.end_datetime - self.start_datetime

    @duration.setter
    def duration(self, value: timedelta):
        self.end_datetime = self.start_datetime + value

    def duration_hms(self) -> Tuple[int, int, int]:
        hours, rem = divmod(self.duration.total_seconds(), 3600)
        minutes, seconds = divmod(rem, 60)
        return int(hours), int(minutes), int(seconds)

    def duration_min(self) -> int:
        return int(self.duration.total_seconds()/60)


@attr.s
class DiveEquipment:
    pdc = attr.ib(factory=DiveComputer, type=DiveComputer)
    suit = attr.ib(default=None, type=DiveSuit)
    weight = attr.ib(default=0, type=int)
    tanks = attr.ib(factory=list, type=list[DiveTank])
    airmixes = attr.ib(factory=list, type=DiveAirMix)


@attr.s
class DiveLogData:
    timestamp_s = attr.ib(default=0.0, type = float)
    depth = attr.ib(default=0.0, type = float)
    temp = attr.ib(default=0.0, type = float)
    pressure = attr.ib(default=0.0, type = float)
    airmix = attr.ib(factory=DiveAirMix, type = DiveAirMix)
    violations = attr.ib(factory=list, type=list[DiveViolation])


@attr.s
class DiveLogEntry:
    dive_num = attr.ib(default=1, type = int)
    location = attr.ib(factory=DiveLogLocation, type=DiveLogLocation)
    diver = attr.ib(default=None, type=Diver)
    buddies = attr.ib(factory=list, type=list[Diver])
    stats = attr.ib(factory=DiveLogStats, type=DiveLogStats)
    equipment = attr.ib(factory=DiveEquipment, type=DiveEquipment)
    data = attr.ib(factory=list, type=list[DiveLogData])
    notes = attr.ib(default="", type=str)
    rating = attr.ib(default=0, type=int)


def add_dive_item(item_list: Dict[str, DiveLogItem], item: DiveLogItem):
    if not item or not item.uuid():
        return None
    uuid = item.uuid()
    if uuid not in item_list:
        item_list[uuid] = item
    return item_list[uuid]


@attr.s
class DiveLogbook:
    diver = attr.ib(default=None, type=dict[Diver])
    locations = attr.ib(factory=dict, type=dict[DiveLogLocation])
    buddies = attr.ib(factory=dict, type=dict[Diver])
    airmix = attr.ib(factory=dict, type=dict[DiveAirMix])
    suits = attr.ib(factory=dict, type=dict[DiveSuit])
    tanks = attr.ib(factory=dict, type=dict[DiveTank])
    pdcs = attr.ib(factory=dict, type=dict[DiveComputer])

    dives = attr.ib(factory=list, type=list[DiveLogEntry])

    def add_airmix(self, item: DiveAirMix):
        return add_dive_item(self.airmix, item)

    def add_dive(self, dive: DiveLogEntry):
        # Add items to the main logbook list if not already there
        buddies = []
        for buddy in dive.buddies:
            new_buddy = add_dive_item(self.buddies, buddy)
            if new_buddy:
                buddies.append(new_buddy)
            dive.buddies = buddies

        dive.location = add_dive_item(self.locations, dive.location)
        dive.equipment.pdc = add_dive_item(self.pdcs, dive.equipment.pdc)
        if dive.equipment.suit:
            dive.equipment.suit = add_dive_item(self.suits, dive.equipment.suit)

        i = 0
        for tank in dive.equipment.tanks:
            if tank:
                dive.equipment.tanks[i] = add_dive_item(self.tanks, tank)
            i = i + 1
        i = 0
        for airmix in dive.equipment.airmixes:
            dive.equipment.airmixes[i] = self.add_airmix(airmix)
            i = i + 1

        self.dives.append(dive)


class Formater(ABC):
    ext = None
    name = None

    def __init__(self, config=None, filename=None):
        self._config = config or DiveLogConfig()
        self.log = logging.getLogger(self.__class__.__name__)
        self.filename = filename
    
    def __repr__(self):
        return f"'{self.name}' ({self.ext})"


class DiveLogFormater(Formater):

    def __init__(self, *args, open_func=None, **kwargs):
        self.temp_path = TemporaryDirectory()
        self.open_func = open_func or open
        super().__init__(*args, **kwargs)

    @abstractmethod
    def read_dives(self, filename: Path) -> DiveLogbook:
        ...

    @abstractmethod
    def write_dives(self, filename: Path, logbook: DiveLogbook):
        ...


class ArchiveFormater(Formater):
    logbook_files = []
    archive_file = None

    def __init__(self, *args, **kwargs):
        self.temp_path = TemporaryDirectory()
        super().__init__(*args, **kwargs)

    def open(self):
        self.logbook_files = self.read_logbooks(self.filename)

    def close(self):
        if self.archive_file:
            self.archive_file.close()

    def save(self):
        self.write_logbooks(self.filename, self.logbook_files)
        self.extracted_path

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def get_log_books(self) -> List[DiveLogbook]:
        return self.logbook_files

    def add_log_books(self, logbooks: List[DiveLogbook]):
        self.logbook_files.extend(logbooks)

    @abstractmethod
    def read_logbooks(self, filename: Path) -> List[DiveLogbook]:
        ...

    @abstractmethod
    def write_logbooks(self, filename: Path, logbooks: List[DiveLogbook], ):
        ...
