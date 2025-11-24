import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfPower
from .coordinator import PvCurtailingCoordinator
from .const import (
    DOMAIN,
    SMA,
    CONF_INJ_TARIFF_ENT_ID,
    CONF_INVERTER_BRAND,
    CONF_IP,
    CONF_PORT,
    CONF_PWR_EXP_ENT_ID,
    CONF_PWR_IMP_ENT_ID,
    CONF_SLAVE_ID,
    COORDINATOR,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    pv_coordinator = hass.data[DOMAIN]

    async_add_entities([SetpointSensor(coordinator=pv_coordinator), InverterPowerSensor(coordinator=pv_coordinator)])
    _LOGGER.info("SunSpec Setpoint sensors were set up")

class SetpointSensor(CoordinatorEntity, SensorEntity): # pyright: ignore[reportIncompatibleVariableOverride]
    """Sensor to store and show power setpoint for inverter"""

    _attr_name = "PV setpoint"
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: PvCurtailingCoordinator) -> None:
        super().__init__(coordinator=coordinator)
        self.coordinator = coordinator
    
    @property
    def native_value(self) -> float | None: # pyright: ignore[reportIncompatibleVariableOverride]
        """Return setpoint so it gets stored by HA in the sensor"""
        return self.coordinator.setpoint_W

class InverterPowerSensor(CoordinatorEntity, SensorEntity): # pyright: ignore[reportIncompatibleVariableOverride]
    """Sensor to store and show production power of inverter"""

    _attr_name = "Inverter power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: PvCurtailingCoordinator) -> None:
        super().__init__(coordinator=coordinator)
        self.coordinator = coordinator

    @property
    def native_value(self) -> float | None: # pyright: ignore[reportIncompatibleVariableOverride]
        """Return power of inverter so it gets storen by HA in the sensor"""
        return self.coordinator.W