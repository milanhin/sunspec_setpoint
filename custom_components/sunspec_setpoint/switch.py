import logging

from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import PvCurtailingCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class CurtailmentSwitch(CoordinatorEntity, SwitchEntity): # pyright: ignore[reportIncompatibleVariableOverride]
    _attr_name = "Curtailment system switch"

    def __init__(self, coordinator: PvCurtailingCoordinator) -> None:
        super().__init__(coordinator=coordinator)
        self.coordinator = coordinator
        self._attr_is_on = self.coordinator.system_switch
    
    @property
    def is_on(self) -> bool: # pyright: ignore[reportIncompatibleVariableOverride]
        return self.coordinator.system_switch
    
    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.system_switch = True
        self.async_write_ha_state()
        _LOGGER.info("Curtailment system was activated")

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.system_switch = False
        self.async_write_ha_state()
        _LOGGER.info("Curtailment system was deactivated")


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    pv_coordinator = hass.data[DOMAIN]
    async_add_entities([CurtailmentSwitch(pv_coordinator)])
    _LOGGER.info("SunSpec setpoint switch was set up")