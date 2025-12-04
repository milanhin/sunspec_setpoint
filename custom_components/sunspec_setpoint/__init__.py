import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .coordinator import PvCurtailingCoordinator
from .const import *

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from ConfigEntry"""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][CONFIG] = entry.data
    _LOGGER.info(entry.data)

    pv_coordinator = PvCurtailingCoordinator(
        hass=hass, config_entry=entry
    )

    hass.data[DOMAIN][COORDINATOR] = pv_coordinator

    await hass.async_add_executor_job(pv_coordinator.sunspec_setup)  # Connect with SunSpec device (blocking call)
    if not pv_coordinator.sunspec_setup_success:
        return False

    # Forward setup to platforms
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry=entry, platforms=["sensor", "switch"])
    )
    return True