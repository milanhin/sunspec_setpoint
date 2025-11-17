import logging
import voluptuous as vol

from datetime import timedelta
from homeassistant.core import HomeAssistant, State
from homeassistant.components.sensor import SensorEntity, PLATFORM_SCHEMA
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfPower
from .coordinator import PvCurtailingCoordinator
from .const import(
    CONF_INJ_TARIFF_ENT_ID,
    CONF_PWR_IMP_ENT_ID,
    CONF_PWR_EXP_ENT_ID,
    CONF_PWR_PV_ENT_ID,
    INJ_CUTOFF_TARIFF,
    CONF_PWR_PV_MAX,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_INJ_TARIFF_ENT_ID): cv.string,
        vol.Required(CONF_PWR_IMP_ENT_ID): cv.string,
        vol.Required(CONF_PWR_EXP_ENT_ID): cv.string,
        vol.Required(CONF_PWR_PV_ENT_ID): cv.string,
        vol.Required(CONF_PWR_PV_MAX): vol.Coerce(int),
    }
)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    
    # initialise coordinator
    pv_coordinator = PvCurtailingCoordinator(
        hass=hass,
        config=config,
    )

    await pv_coordinator.async_refresh()  # call _async_update_data() of coordinator

    async_add_entities([SetpointSensor(coordinator=pv_coordinator)])
    _LOGGER.info("SunSpec Setpoint platform was set up")

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