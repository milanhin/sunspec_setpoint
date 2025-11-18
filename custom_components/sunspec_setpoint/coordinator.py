import logging
import datetime
import requests
import aiohttp
import sunspec2.modbus.client as client

from typing import Any
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.core import HomeAssistant, State
from homeassistant import config_entries

from .const import(
    CONF_INJ_TARIFF_ENT_ID,
    CONF_PWR_IMP_ENT_ID,
    CONF_PWR_EXP_ENT_ID,
    CONF_INVERTER_BRAND,
    INJ_CUTOFF_TARIFF,
    INVERTER_SINGLE_PHASE_MID,
    INVERTER_THREE_PAHSE_MID,
    INVERTER_SPLIT_PHASE_MID,
    CONTROLS_MID,
    NAMEPLATE_MID,
    WRTG_OFFSET,
    WMAXLIMPCT_OFFSET,
    W_OFFSET,
    CONF_IP,
    CONF_PORT,
    CONF_SLAVE_ID,
    SMA,
)

_LOGGER = logging.getLogger(__name__)

class PvCurtailingCoordinator(DataUpdateCoordinator):
    def __init__(
            self,
            hass: HomeAssistant,
            config: ConfigType,
    ) -> None:
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="PV_Curtailing_coordinator",
            config_entry=None,
            update_interval=datetime.timedelta(seconds=20),
        )

        _LOGGER.info("Coordinator for SunSpec setpoint initialised")
        self.setpoint_W: int | None = None      # Holds setpoint in Watt
        self.last_setpoint_W: int | None = None # Last sent setpoint
        self.W: float | None = None             # Holds power of inverter
        self.setpoint_pct: float | None = None  # Holds setpoint in percentage
        self.d = None                           # SunSpec client device
        self.WRtg: int | None = None           # Rated inverter power

        # unpack config
        self.inj_trf_ent_id: str = config[CONF_INJ_TARIFF_ENT_ID]
        self.pwr_imp_ent_id: str = config[CONF_PWR_IMP_ENT_ID]
        self.pwr_exp_ent_id: str = config[CONF_PWR_EXP_ENT_ID]
        self.IP:             str = config[CONF_IP]
        self.PORT                = int(config[CONF_PORT])
        self.SLAVE_ID            = int(config[CONF_SLAVE_ID])
        self.brand               = str(config[CONF_INVERTER_BRAND]).lower()
    
    async def _async_setup(self) -> None:
        """Set up coordinator"""

    def sunspec_setup(self) -> None:
        """Setup coordinator and connect to SunSpec device for config through yaml"""

        _LOGGER.info("Setting sunspec connection")
        # Connect to inverter with sunspec
        try:
            self.d = client.SunSpecModbusClientDeviceTCP(slave_id=self.SLAVE_ID, ipaddr=self.IP, ipport=self.PORT)
            self.d.scan()
        except Exception as e:
            _LOGGER.error(f"Setpoint integration failed to connect to SunSpec device, error: {e}")
            return
        
        # Check which model to use for measurands
        self.measurands_mid = self.check_measurand_model(d=self.d)

        # Read rated power
        rating = self.offset_read(d=self.d, mid=NAMEPLATE_MID, trg_offset=WRTG_OFFSET)
        if rating != None:
            self.WRtg = int(rating)
        _LOGGER.info(f"Max rated power read from sunspec: {rating} W")
    
    async def _async_update_data(self) -> dict[str, Any]:
        if self.d == None:
            try:
                self.d = client.SunSpecModbusClientDeviceTCP(slave_id=self.SLAVE_ID, ipaddr=self.IP, ipport=self.PORT)
                self.d.scan()
            except Exception as e:
                _LOGGER.error(f"Setpoint integration failed to connect to SunSpec device, error: {e}")
                return {}

        inj_tariff_state = self.hass.states.get(self.inj_trf_ent_id)
        pwr_import_state = self.hass.states.get(self.pwr_imp_ent_id)
        pwr_export_state = self.hass.states.get(self.pwr_exp_ent_id)

        # temporary type fix
        if (
            inj_tariff_state == None or
            pwr_import_state == None or
            pwr_export_state == None
        ):
            _LOGGER.error("Entity needed for setpoint has no value")
            return {}

        # Read data from dependant sensors
        inj_tariff = float(inj_tariff_state.state)
        pwr_import = self.convert_pwr_state_to_watt(pwr_import_state)
        pwr_export = self.convert_pwr_state_to_watt(pwr_export_state)

        # Read inverter power through SunSpec
        self.W = self.offset_read(d=self.d, mid=self.measurands_mid, trg_offset=W_OFFSET)
        
        # Calculate setpoints for inverter power and send it to inverter
        if self.W != None and self.WRtg != None:
            self.setpoint_W = self.calc_setpoint_W(inj_tariff, pwr_import, pwr_export, self.W, pwr_rated=self.WRtg)
            self.setpoint_pct = self.calc_setpoint_pct(sp_W=self.setpoint_W, pwr_rated=self.WRtg)
            if not (self.last_setpoint_W == self.WRtg and self.setpoint_W == self.WRtg):  # Don't keep sending 100% setpoints       
                self.write_setpoint(d=self.d, sp_pct=self.setpoint_pct)

        return {
            "setpoint_W": self.setpoint_W,
            "setpoint_pct": self.setpoint_pct,
        }
    
    def convert_pwr_state_to_watt(self, state: State) -> float:
        value = float(state.state)
        unit = state.attributes.get("unit_of_measurement", None)
        if unit == "kW":
            return value * 1e3
        elif unit == "W":
            return value
        elif unit == "mW" or unit == "MW":
            return value / 1e3
        else:
            _LOGGER.error(f"Provided power entity {state.entity_id} has no known unit")
            return 0
    
    def calc_setpoint_W(self, inj_tariff: float, pwr_import: float, pwr_export: float, pwr_PV: float, pwr_rated: float) -> int:
        if inj_tariff >= INJ_CUTOFF_TARIFF:
            return round(pwr_rated)
        
        if pwr_import > 5 and inj_tariff < INJ_CUTOFF_TARIFF:
            sp = min(pwr_PV + pwr_import, pwr_rated)  # don't go above max power
            _LOGGER.info(f"PV setpoint sent during curtailing and importing from grid, PV: {pwr_PV} W, import: {pwr_import} W, export: {pwr_export} W, setpoint: {sp} W")
            return round(sp)

        else: # injecting during negative price
            sp = max(pwr_PV - pwr_export, 0)  # no negative power
            _LOGGER.info(f"PV setpoint sent during curtailing and exporting to grid, PV: {pwr_PV} W, import: {pwr_import} W, export: {pwr_export} W, setpoint: {sp} W")
            return round(sp)
    
    def calc_setpoint_pct(self, sp_W: int, pwr_rated: float) -> float:
        """Calc setpoint in percentage from setpoint in Watt"""
        sp_pct = (sp_W / pwr_rated) * 100
        return round(sp_pct, 2)  # percentage with 2 decimals
    
    def offset_read(self, d, mid: int, trg_offset: int) -> float | None:
        for name, point in d.models[mid][0].points.items():
            if point.offset == trg_offset:
                point.read()
                val = point.cvalue
                return val
        _LOGGER.error("SunSpec point was not found and could not be read")
        return None
    
    def check_measurand_model(self, d) -> int:
        if INVERTER_SINGLE_PHASE_MID in d.models:
            return INVERTER_SINGLE_PHASE_MID
        if INVERTER_SPLIT_PHASE_MID in d.models:
            return INVERTER_SPLIT_PHASE_MID
        if INVERTER_THREE_PAHSE_MID in d.models:
            return INVERTER_THREE_PAHSE_MID
        _LOGGER.error("No measurands model found on SunSpec device")
        return 0
    
    def write_setpoint(self, d, sp_pct: float) -> None:
        for name, point in d.models[CONTROLS_MID][0].points.items():
            if point.offset == WMAXLIMPCT_OFFSET:
                point.read()
                if self.brand == SMA:
                    point.cvalue = sp_pct
                    try:
                        point.write()
                        _LOGGER.info(f"Setpoint sent to inverter: {sp_pct} %")
                        self.last_setpoint_W = self.setpoint_W
                    except Exception as e:
                        _LOGGER.error(f"Failed to write setpoint to inverter: {e}")
                        return
                else:
                    _LOGGER.error("Writing setpoint to this inverter brand is not implemented")
                    return