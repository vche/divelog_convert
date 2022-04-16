from sre_constants import LITERAL
import attr
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum


class DiveViolation(Enum):
    ASCENT="Ascent rate violation"
    DECO="Decompression violation"


class DiveUnitDistance(Enum):
    METER="m"
    FEET="ft"


class DiveUnitTemperature(Enum):
    CELSIUS="C"
    FAHRENHEIT="F"
    KERVIN="K"


class DiveUnitPressure(Enum):
    BAR="bar"
    PSI="psi"


class DiveUnitVolume(Enum):
    LITER="L"
    CUBICFEET="CF"


class DiveLogItem:
    def uuid(self):
        return f"{self.__class__.__name__.lower()}-{self.strid()}".replace(" ","_")
    
    def strid(self):
        return ""

@attr.s
class DiveLogConfig:
    # TODO load defaults from config file
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
        return f"{self.first_name} {self.last_name}"


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
    airmix = attr.ib(factory=DiveAirMix, type=DiveAirMix)

    def strid(self):
        return f"{self.name} {self.volume}"


@attr.s
class DiveComputer(DiveLogItem):
    dive_num = attr.ib(default=1, type = int)
    manufacturer = attr.ib(default="", type = str)
    firmware = attr.ib(default="", type = str)
    type = attr.ib(default=None, type=str)
    sn = attr.ib(default=None, type=str)
    sampling_period = attr.ib(default=1, type=int)

    def strid(self):
        return f"{self.type} {self.sn}"


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
    tanks = attr.ib(factory=list, type=DiveTank)
    weight = attr.ib(default=0, type=int)


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
    location = attr.ib(factory=DiveLogLocation, type=DiveLogLocation)
    diver = attr.ib(factory=list, type=Diver)
    buddies = attr.ib(factory=list, type=list[Diver])
    stats = attr.ib(factory=DiveLogStats, type=DiveLogStats)
    equipment = attr.ib(factory=DiveEquipment, type=DiveEquipment)
    data = attr.ib(factory=list, type=list[DiveLogData])
    notes = attr.ib(default="", type=str)
    rating = attr.ib(default=0, type=int)


class DiveLogFormater(ABC):

    @property
    @abstractmethod
    def ext(self):
        ...

    @property
    @abstractmethod
    def name(self):
        ...

    def __init__(self, config=None):
        self._config = config or DiveLogConfig()
        self.log = logging.getLogger(self.__class__.__name__)
    
    def __repr__(self):
        return f"'{self.name}' ({self.ext})"

    @abstractmethod
    def read_dives(self, filename: Path) -> List[DiveLogEntry]:
        ...

    @abstractmethod
    def write_dives(self, filename: Path, dives: List[DiveLogEntry]):
        ...
