import logging

from homeassistant.core import HomeAssistant
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    async_add_entities([SetpointNumber()])
    _LOGGER.info("SunSpec Setpoint platform was set up")
    
class SetpointNumber(NumberEntity):
    _attr_name = "test_input"
    _attr_min_value = 0 # pyright: ignore[reportAssignmentType]
    _attr_max_value = 1000 # pyright: ignore[reportAssignmentType]

    def __init__(self) -> None:
        super().__init__()

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        _LOGGER.info(f"Number setpoint sent from code with value {value}.")
    
