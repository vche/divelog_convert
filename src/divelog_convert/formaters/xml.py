from asyncio import PidfdChildWatcher
import logging
from numpy import isin
import xmltodict
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
from datetime import date, datetime, timedelta

from divelog_convert.formater import (
    DiveSuit,
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
    DiveUnitTemperature,
    DiveViolation
)


def datetime_from_iso(datestr: str, logger: logging.Logger) -> datetime:
    # Try to convert from iso string with then without timezone , and sypport "z", not supported by fromisoformat()
    return datetime.fromisoformat(datestr.replace("Z", ""))

def list_append_uniq(value_list, value):
    # Append a value to an array only if it is not already here
    if value not in value_list:
        value_list.append(value)


def get_list_for_item(items_dict: Dict[str, Any], item: Any) -> List[Any]:
    items = items_dict.get(item, [])
    return items if isinstance(items, list) else [items]


def set_if_changed(new_dict: Dict[str, Any], old_dict: Dict[str, Any], key: str, value: Any):
    if not old_dict or old_dict.get(key) != value:
        if isinstance(value, float):
            value = f"{value:.2f}"
        new_dict[key] = value


class XmlDiveLogFormater(DiveLogFormater):

    def read_dives(self, filename: Path) -> Tuple[int, DiveLogbook]:
        with self.open_func(filename, "r") as dive_file:
            self.log.info(f"Reading dives from {filename}")
            raw_content = dive_file.read()
            content = raw_content.decode() if isinstance(raw_content, bytes) else raw_content
            dive_dict = xmltodict.parse(content)
            errors, logbook = self.parse_xml_dict(dive_dict)
            self.log.info(f"{len(logbook.dives)} dives read from {filename}, {errors} errors")
            return logbook

    def write_dives(self, filename: Path, logbook: DiveLogbook):
        if filename.suffix != self.ext:
            filename = filename.with_suffix(self.ext)

        with open(filename, "w") as dive_file:
            self.log.info(f"Writing {len(logbook.dives)} dives to {filename}")
            dive_dict = self.build_xml_dict(logbook)
            xml_data = xmltodict.unparse(dive_dict, pretty=True, indent="    ")
            dive_file.write(xml_data)

    @abstractmethod
    def parse_xml_dict(self, xml_dict: Dict[str, Any]) -> List[DiveLogEntry]:
        ...

    @abstractmethod
    def build_xml_dict(self, entry: DiveLogEntry) -> Dict[str, Any]:
        ...



class UddfDiveLogFormater(XmlDiveLogFormater):
    ext = ".uddf"
    name = "uddf"

    UDDF_VIOLATIONS = {
        DiveViolation.ASCENT: "ascent",
        DiveViolation.DECO: "deco",
        DiveViolation.SURFACE: "surface",
        DiveViolation.ERROR: "error",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ref_dict = {}

    def _get_uddf_violation(self, violation: DiveViolation) -> str:
        return self.UDDF_VIOLATIONS.get(violation, self.UDDF_VIOLATIONS[DiveViolation.ERROR])

    def _get_uddf_violation_from_str(self, str_violation: str) -> DiveViolation:
        for viol in self.UDDF_VIOLATIONS:
            if str_violation == self.UDDF_VIOLATIONS[viol]:
                return viol
        return DiveViolation.ERROR

    def _parse_owner(self, logbook: DiveLogbook, owner_dict: Dict[str, Any]):
        if owner_dict:
            logbook.diver = Diver(
                first_name=owner_dict['personal']['firstname'] or self._config.diver_first_name,
                last_name=owner_dict['personal']['lastname'] or self._config.diver_last_name,
            )

            equipment = owner_dict.get('equipment')
            if equipment:
                for pdc in get_list_for_item(equipment, 'divecomputer'):
                    pdc_obj = DiveComputer(
                        manufacturer = pdc.get("manufacturer"),
                        type = pdc.get("name"),
                        sn = pdc.get("serialnumber")
                    )
                    logbook.pdcs[pdc_obj.uuid()] = pdc_obj
                    self._ref_dict[pdc['@id']] = pdc_obj

                for suit in get_list_for_item(equipment, 'suit'):
                    suit_obj = DiveSuit(name = suit.get("name"), type = suit.get("suittype"))
                    logbook.suits[suit_obj.uuid()] = suit_obj
                    self._ref_dict[suit['@id']] = suit_obj

                for tank in get_list_for_item(equipment, 'tank'):
                    tank_obj = DiveTank(name = tank.get("name"), volume = tank.get("tankvolume"))
                    logbook.tanks[tank_obj.uuid()] = tank_obj
                    self._ref_dict[tank['@id']] = tank_obj

    def _parse_buddies(self, logbook: DiveLogbook, buddies: Optional[Dict[Union[str, Any], List[Dict[str, Any]]]]):
        if buddies:
            buddies_list = buddies if isinstance(buddies, list) else [buddies]
            for bud in buddies_list:
                if 'firstname' in bud['personal'] and 'lastname' in bud['personal']:
                    bud_obj = Diver(first_name=bud['personal']['firstname'], last_name=bud['personal']['lastname'])
                    logbook.buddies[bud_obj.uuid()] = bud_obj
                    self._ref_dict[bud['@id']] = bud_obj

    def _parse_locations(self, logbook: DiveLogbook, locs: Optional[Dict[str, Any]]):
        if locs:
            loc_list = locs if isinstance(locs, list) else [locs]
            for loc in loc_list:
                geo = loc.get("geography", {})
                addr = geo.get("address", {})
                loc_obj = DiveLogLocation(
                    divesite = loc.get("name"),
                    gps = (geo.get("latitude"), geo.get("longitude")),
                    locname = geo.get("location"),
                    city = addr.get("city"),
                    state_province = addr.get("province"),
                    street = addr.get("street"),
                    country = addr.get("country"),
                )
                logbook.locations[loc_obj.uuid()] = loc_obj
                self._ref_dict[loc['@id']] = loc_obj

    def _parse_gas(self, logbook: DiveLogbook, gas: Optional[Dict[Union[str, Any], List[Dict[str, Any]]]]):
        if gas:
            gas_list = gas if isinstance(gas, list) else [gas]
            for gas in gas_list:
                gas_obj = DiveAirMix(
                    name=gas['name'],
                    o2=float(gas.get('o2', 0.0)),
                    n2=float(gas.get('n2', 0.0)),
                    h2=float(gas.get('h2', 0.0)),
                    he=float(gas.get('he', 0.0)),
                    ar=float(gas.get('ar', 0.0)),
                )
                logbook.airmix[gas_obj.uuid()] = gas_obj
                self._ref_dict[gas['@id']] = gas_obj

    def _parse_dives(self, logbook: DiveLogbook, dives: Optional[Dict[Union[str, Any], List[Dict[str, Any]]]]):
        errors = 0
        for group in get_list_for_item(dives, 'repetitiongroup'):
            dives = group['dive'] if isinstance(group['dive'], list) else [group['dive']]            
            for dive in dives:
                try:
                    self._parse_dive(logbook, dive)
                except KeyError as e:
                    self.log.error(f"Cannot parse dive: {e}")
                    self.exception(e)
                    errors = errors + 1
        return errors

    def _process_link(self, logbook: DiveLogbook, dive: DiveLogEntry, links: Union[Dict[str,Any], List[Dict[str,Any]]]):
        if links:
            links_list = links if isinstance(links, list) else [links]
        else:
            links_list = []
        
        for link in links_list:
            ref = link.get("@ref")
            target = self._ref_dict.get(ref)
            
            if target:
                if isinstance(target, Diver):
                    list_append_uniq(dive.buddies, target)
                elif isinstance(target, DiveLogLocation):
                    dive.location = target
                elif isinstance(target, DiveComputer):
                    dive.equipment.pdc = target
                elif isinstance(target, DiveSuit):
                    dive.equipment.suit = target
                elif isinstance(target, DiveAirMix):
                    list_append_uniq(dive.equipment.airmixes, target)
                elif isinstance(target, DiveTank):
                    list_append_uniq(dive.equipment.tanks, target)

    def _get_sample_violations(self, dive_sample: Dict[str, Any]) -> set:
        violations = set()
        for elt in get_list_for_item(dive_sample, 'alarm'):
            violations.add(self._get_uddf_violation_from_str(elt))
        return violations

    def _get_sample_temperature(self, last_datapoint: DiveLogData, dive_sample: Dict[str, Any]):
        temp = dive_sample.get('temperature')
        if temp is not None:
            temp = self._config.unit_temperature.from_unit(
                DiveUnitTemperature.KELVIN, float(dive_sample['temperature'])
            )
        elif last_datapoint:
            temp = last_datapoint.temp
        else:
            temp = 0
        return temp

    def _get_sample_airmix(self, logbook: DiveLogbook, last_datapoint: DiveLogData, dive_sample: Dict[str, Any]):
        # If no airmix (should be in the first sample), use previous sample,or from logbook or default to air
        airmix_link = dive_sample.get('switchmix', {}).get("@ref")
        if airmix_link:
            airmix = self._ref_dict.get(airmix_link)
        elif last_datapoint:
            airmix = last_datapoint.airmix
        elif logbook.airmix:
            airmix = list(logbook.airmix.values())[0]
        else:
            airmix = DiveAirMix()
            logbook.add_airmix(airmix)
        return airmix

    def _get_sample_tankpressure(self, last_datapoint: DiveLogData, dive_sample: Dict[str, Any]):
        float(dive_sample['tankpressure']) if dive_sample.get('tankpressure') is not None else None,
        tank_pressure = dive_sample.get('tankpressure')
        if tank_pressure is not None:
            tank_pressure = dive_sample['tankpressure']
        elif last_datapoint:
            tank_pressure = last_datapoint.pressure
        else:
            tank_pressure = None
        return tank_pressure

    def _get_sample_depth(self, last_datapoint: DiveLogData, dive_sample: Dict[str, Any]):
        if dive_sample.get('depth') is not None:
            depth = float(dive_sample['depth'])
        elif last_datapoint:
            depth = last_datapoint.depth
        else:
            depth = 0.0
        return depth

    def _get_sample_timestamp(self, last_datapoint: DiveLogData, dive_sample: Dict[str, Any]):
        if dive_sample.get('divetime') is not None:
            ts = float(dive_sample['divetime'])
        elif last_datapoint:
            ts = last_datapoint.timestamp_s
        else:
            ts = 0.0
        return ts

    def _parse_dive_data(
        self, logbook: DiveLogbook, dive_samples: Dict[str, Any]
    ) -> Tuple[int, List[DiveViolation], List[DiveLogData]]:
        dive_data = []
        all_violations = set()
        last_ts = None
        global_period = 0
        last_datapoint = None
        for dive_sample in dive_samples.get("waypoint", []):
            ts = depth = self._get_sample_timestamp(last_datapoint, dive_sample)
            depth = self._get_sample_depth(last_datapoint, dive_sample)
            temp = self._get_sample_temperature(last_datapoint, dive_sample)
            airmix = self._get_sample_airmix(logbook, last_datapoint, dive_sample)
            tank_pressure = self._get_sample_tankpressure(last_datapoint, dive_sample)

            # Compute violation in this sample and overall during the dive
            violations = self._get_sample_violations(dive_sample)
            all_violations.union(violations)

            # Sum up sample periods
            if last_ts:
                global_period += (ts - last_ts)
            last_ts = ts

            # Create datapoint
            last_datapoint = DiveLogData(
                timestamp_s = ts,
                depth = depth,
                temp = temp,
                airmix= airmix,
                pressure = tank_pressure,
                violations = list(violations),
            )
            dive_data.append(last_datapoint)

        # Compute average sampling period
        sampling_period = round(global_period/(len(dive_data)-1)) if len(dive_data)>0 else 0

        return sampling_period, list(all_violations), dive_data

    def _build_dive_data(self, dive: DiveLogEntry) -> List[Dict[str, Any]]:
        dive_waypoints = []
        last_waypoint = None
        last_airmix = None
        for dive_sample in dive.data:
            dive_waypoint = { "divetime": int(dive_sample.timestamp_s) }
            set_if_changed(dive_waypoint, last_waypoint, "depth", dive_sample.depth)
            set_if_changed(dive_waypoint, last_waypoint, "tankpressure", dive_sample.pressure)
            if last_airmix != dive_sample.airmix.uuid():
                last_airmix = dive_sample.airmix.uuid()
                dive_waypoint["switchmix"] = {"@ref": last_airmix}
            set_if_changed(
                dive_waypoint, last_waypoint, "temperature", 
                self._config.unit_temperature.to_unit(DiveUnitTemperature.KELVIN, dive_sample.temp)
            )

            if dive_sample.violations:
                dive_waypoint["alarm"] = []
                for elt in dive_sample.violations:
                    dive_waypoint["alarm"].append(self._get_uddf_violation(elt))

            dive_waypoints.append(dive_waypoint)
            last_waypoint = dive_waypoint
        return dive_waypoints

    def _dive_to_dict(self, dive: DiveLogEntry, logbook: DiveLogbook):
        dive_dict = { 
            "informationbeforedive": {"equipmentused": {}},
            "tankdata": {},
            "samples": [],
            "informationafterdive": { "rating": {}},
        }
        dive_dict["informationbeforedive"]["divenumber"] = dive.dive_num
        dive_dict["informationbeforedive"]["airtemperature"] = self._config.unit_temperature.to_unit(
            DiveUnitTemperature.KELVIN, dive.stats.airtemp
        )
        dive_dict["informationbeforedive"]["link"] = []
        for buddy in dive.buddies:
            dive_dict["informationbeforedive"]["link"].append({ "@ref": buddy.uuid()})

        dive_dict["informationbeforedive"]["datetime"] = dive.stats.start_datetime.isoformat()
        dive_dict["informationbeforedive"]["equipmentused"]["leadquantity"] = dive.equipment.weight
        if dive.location:
            dive_dict["informationbeforedive"]["link"].append({ "@ref": dive.location.uuid()})

        dive_dict["tankdata"]["tankpressurebegin"] = dive.stats.pressure_in
        dive_dict["tankdata"]["tankpressureend"] = dive.stats.pressure_out

        dive_dict["samples"] = {    "waypoint": self._build_dive_data(dive) }

        dive_dict["informationafterdive"]["rating"]["ratingvalue"] = dive.rating
        dive_dict["informationafterdive"]["greatestdepth"] = dive.stats.maxdepth
        dive_dict["informationafterdive"]["averagedepth"] = dive.stats.avgdepth
        dive_dict["informationafterdive"]["lowesttemperature"] = self._config.unit_temperature.to_unit(
                    DiveUnitTemperature.KELVIN, dive.stats.mintemp
                ),
        dive_dict["informationafterdive"]["diveduration"] = dive.stats.duration.total_seconds()
        if dive.notes:
            dive_dict["informationafterdive"]["notes"] = { "para": dive.notes }

        return dive_dict

    def _parse_dive(self, logbook: DiveLogbook, dive: Dict[str, Any]):
        # Collect dive information and tank data
        equipment_used = dive["informationbeforedive"].get("equipmentused", {})
        equipment_used.update(dive["informationafterdive"].get("equipmentused", {}))
        tankdata = dive.get("tankdata", {})

        # Build the dive data
        sampling_period, all_violations, dive_data = self._parse_dive_data(logbook, dive.get("samples", {}))

        notes = dive["informationafterdive"].get("notes", {})
        if "para" in notes:
            notes = notes["para"]

        if len(dive_data) > 0 and dive_data[0].temp is not None:
            surfacetemp = self._config.unit_temperature.to_unit(DiveUnitTemperature.KELVIN, dive_data[0].temp)
        else:
            surfacetemp = None

        # Build the dive entry
        dive_entry = DiveLogEntry(
            dive_num = dive["informationbeforedive"]["divenumber"],
            diver = logbook.diver,
            stats = DiveLogStats(
                start_datetime = datetime_from_iso(dive["informationbeforedive"].get("datetime"), self.log),
                maxdepth = dive["informationafterdive"].get("greatestdepth", 0.0),
                avgdepth = dive["informationafterdive"].get("averagedepth", 0.0),
                mintemp = self._config.unit_temperature.from_unit(
                    DiveUnitTemperature.KELVIN, dive["informationafterdive"].get("lowesttemperature")
                ),
                pressure_in = float(tankdata.get("tankpressurebegin", 0.0)),
                pressure_out = float(tankdata.get("tankpressureend", 0.0)),
                violations = all_violations,
                airtemp = self._config.unit_temperature.from_unit(
                    DiveUnitTemperature.KELVIN, dive["informationbeforedive"].get("airtemperature")
                ),
                surfacetemp = surfacetemp,
                visibility = dive["informationafterdive"].get("visibility", 0.0),
            ),
            equipment = DiveEquipment(weight = int(equipment_used.get("leadquantity", 0))),
            notes = notes,
            rating = dive["informationafterdive"].get("rating", {}).get("ratingvalue"),
            data = dive_data,
        )
        dive_entry.stats.duration = timedelta(seconds = float(dive["informationafterdive"].get("diveduration", 0)))
        dive_entry.equipment.pdc.sampling_period = sampling_period

        # Update the dive with the references
        self._process_link(logbook, dive_entry, dive["informationbeforedive"].get("link"))
        self._process_link(logbook, dive_entry, dive["informationafterdive"].get("link"))
        self._process_link(logbook, dive_entry, dive["informationbeforedive"].get("equipmentused", {}).get("link"))
        self._process_link(logbook, dive_entry, dive["informationafterdive"].get("equipmentused", {}).get("link"))
        self._process_link(logbook, dive_entry, tankdata.get("link"))

        logbook.add_dive(dive_entry)

    def _diver_to_dict(self, diver: Diver, logbook: Optional[DiveLogbook] = None):
        diver_dict = { 
            "@id": diver.uuid(),
            "personal": { "firstname": diver.first_name, "lastname": diver.last_name },
            "equipment": {},
        }

        # If logbook is specifiedm assume it's the owner, add its equipment
        if logbook:
            if logbook.pdcs:
                diver_dict["equipment"]['divecomputer'] = []
                for pdc in logbook.pdcs.values():
                    diver_dict["equipment"]['divecomputer'].append({
                        "@id": pdc.uuid(),
                        "name": pdc.type,
                        "manufacturer": { "name": pdc.manufacturer },
                        "serialnumber": pdc.sn,
                    })
            if logbook.suits:
                diver_dict["equipment"]['suit'] = []
                for suit in logbook.suits.values():
                    diver_dict["equipment"]['suit'].append({
                        "@id": suit.uuid(),
                        "name": suit.name,
                        "suittype": suit.type,
                    })
            if logbook.tanks:
                diver_dict["equipment"]['tank'] = []
                for tank in logbook.tanks.values():
                    diver_dict["equipment"]['tank'].append({
                        "@id": tank.uuid(),
                        "name": tank.name,
                        "tankvolume": tank.volume,
                    })
        return diver_dict

    def _location_to_dict(self, location: DiveLogLocation):
        loc_dict = {
            "@id": location.uuid(),
            "name": location.divesite,
            "geography": {"location": location.locname, "address": {}}
        }
        if location.gps:
            lat,long = location.gps
            loc_dict["geography"]["latitude"] = lat
            loc_dict["geography"]["longitude"] = long
        if location.street:
            loc_dict["geography"]["address"]["street"] = location.street
        if location.city:
            loc_dict["geography"]["address"]["city"] = location.city
        if location.state_province:
            loc_dict["geography"]["address"]["province"] = location.state_province
        if location.country:
            loc_dict["geography"]["address"]["country"] = location.country
        return loc_dict

    def _airmix_to_dict(self, airmix: DiveAirMix):
        return { 
            "@id": airmix.uuid(),
            "name": airmix.name,
            "o2": airmix.o2,
            "n2": airmix.n2,
            "he": airmix.he,
            "ar": airmix.ar,
            "h2": airmix.h2,
        }

    def parse_xml_dict(self, xml_dict: Dict[str, Any]) -> Tuple[int, DiveLogbook]:
        logbook = DiveLogbook(config=self._config)
        udf_data = xml_dict['uddf']
        self._parse_owner(logbook, udf_data.get('diver', {}).get('owner'))
        self._parse_buddies(logbook, udf_data.get('diver', {}).get('buddy'))
        self._parse_locations(logbook, udf_data.get('divesite', {}).get("site"))
        self._parse_gas(logbook, udf_data.get('gasdefinitions', {}).get("mix"))
        errors = self._parse_dives(logbook, udf_data.get("profiledata"))

        return errors, logbook

    def build_xml_dict(self, logbook: DiveLogbook) -> Dict[str, Any]:
        logbook_dict = {
            "uddf": {
                "@xmlns": "http://www.streit.cc/uddf/3.2/",
                "@version": "3.2.1",
                "generator": {
                    "name": "divelog_convert",
                    "type": "logbook",
                    "datetime": datetime.now().isoformat(),
                    "manufacturer": {
                        "@id": "divelog_convert",
                        "name": "Vivien Chene",
                        "contact": {"homepage": "https://github.com/vche/divelog_convert"}
                    },
                    "version": self._config.app_version,
                },
                # "mediadata": {},
                "diver": {},
                # first dive in repet group: <surfaceintervalbeforedive><infinity></infinity> </surfaceintervalbeforedive>
                # <surfaceintervalbeforedive><passedtime>11580</passedtime></surfaceintervalbeforedive>
            }
        }    
        logbook_dict["uddf"]["diver"]["owner"] = self._diver_to_dict(logbook.diver, logbook=logbook)
        if logbook.buddies:
            logbook_dict["uddf"]["diver"]["buddy"] = []
            for buddy in logbook.buddies.values():
                logbook_dict["uddf"]["diver"]["buddy"].append(self._diver_to_dict(buddy))

        if logbook.locations:
            logbook_dict["uddf"]["divesite"] = {"site": []}
            for loc in logbook.locations.values():
                logbook_dict["uddf"]["divesite"]["site"].append(self._location_to_dict(loc))

        if logbook.airmix:
            logbook_dict["uddf"]["gasdefinitions"] = {"mix": []}
            for loc in logbook.airmix.values():
                logbook_dict["uddf"]["gasdefinitions"]["mix"].append(self._airmix_to_dict(loc))
        
        logbook_dict["uddf"]["profiledata"] = []
        for dive in logbook.dives:
            logbook_dict["uddf"]["profiledata"].append(
                { "repetitiongroup": [{"dive": self._dive_to_dict(dive, logbook)}] }
            )

        return logbook_dict
