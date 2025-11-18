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
    CONF_PWR_PV_ENT_ID,
    INJ_CUTOFF_TARIFF,
    CONF_PWR_PV_MAX,
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
            update_interval=datetime.timedelta(seconds=30),
        )

        _LOGGER.info("Coordinator for SunSpec setpoint initialised")
        self.setpoint_W: int | None = None      # Holds setpoint in Watt
        self.setpoint_pct: float | None = None  # Holds setpoint in percentage
        self.d = None  # SunSpec client device

        # unpack config
        self.pwr_ent_ids = {}
        self.inj_trf_ent_id: str = config[CONF_INJ_TARIFF_ENT_ID]
        self.pwr_imp_ent_id: str = config[CONF_PWR_IMP_ENT_ID]
        self.pwr_exp_ent_id: str = config[CONF_PWR_EXP_ENT_ID]
        self.pwr_pv_ent_id: str = config[CONF_PWR_PV_ENT_ID]
        self.pwr_pv_max: int = config[CONF_PWR_PV_MAX]
    
    async def _async_setup(self) -> None:
        """Set up coordinator"""

    def sunspec_setup(self) -> None:
        _LOGGER.info("Setting sunspec connection")
        # Connect to inverter with sunspec
        try:
            self.d = client.SunSpecModbusClientDeviceTCP(slave_id=126, ipaddr="192.168.1.170", ipport=502)
            self.d.scan()
        except Exception as e:
            _LOGGER.error(f"Setpoint integration failed to connect to SunSpec device, error: {e}")
            return
        
        WRtg = self.d.models[120][0].WRtg.value
        WRtg_SF = self.d.models[120][0].WRtg_SF.value
        rating = WRtg * 10 ** WRtg_SF
        self.pwr_pv_max = rating
        _LOGGER.info(f"Max rated power read from sunspec: {rating} W")
    
    async def _async_update_data(self) -> dict[str, Any]:
        inj_tariff_state = self.hass.states.get(self.inj_trf_ent_id)
        pwr_import_state = self.hass.states.get(self.pwr_imp_ent_id)
        pwr_export_state = self.hass.states.get(self.pwr_exp_ent_id)
        pwr_PV_state = self.hass.states.get(self.pwr_pv_ent_id)

        # temporary type fix
        if (
            inj_tariff_state == None or
            pwr_import_state == None or
            pwr_export_state == None or
            pwr_PV_state == None 
        ):
            _LOGGER.error("Entity needed for setpoint has no value")
            return {}

        inj_tariff = float(inj_tariff_state.state)
        pwr_import = self.convert_pwr_state_to_watt(pwr_import_state)
        pwr_export = self.convert_pwr_state_to_watt(pwr_export_state)
        pwr_PV     = self.convert_pwr_state_to_watt(pwr_PV_state)
        
        self.setpoint_W = self.calc_setpoint_W(inj_tariff, pwr_import, pwr_export, pwr_PV)
        self.setpoint_pct = self.calc_setpoint_pct(sp_W=self.setpoint_W)

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
    
    def calc_setpoint_W(self, inj_tariff: float, pwr_import: float, pwr_export: float, pwr_PV: float) -> int:
        max_PV_power = self.pwr_pv_max
        if inj_tariff >= INJ_CUTOFF_TARIFF:
            return round(max_PV_power)
        
        if pwr_import > 5 and inj_tariff < INJ_CUTOFF_TARIFF:
            sp = min(pwr_PV + pwr_import, max_PV_power)  # don't go above max power
            _LOGGER.info(f"PV setpoint sent during curtailing and importing from grid, PV: {pwr_PV} W, import: {pwr_import} W, export: {pwr_export} W, setpoint: {sp} W")
            return round(sp)

        else: # injecting during negative price
            sp = max(pwr_PV - pwr_export, 0)  # no negative power
            _LOGGER.info(f"PV setpoint sent during curtailing and exporting to grid, PV: {pwr_PV} W, import: {pwr_import} W, export: {pwr_export} W, setpoint: {sp} W")
            return round(sp)
    
    def calc_setpoint_pct(self, sp_W: int) -> float:
        """Calc setpoint in percentage from setpoint in Watt"""
        sp_pct = (sp_W / self.pwr_pv_max) * 100
        return round(sp_pct, 2)  # percentage with 2 decimals