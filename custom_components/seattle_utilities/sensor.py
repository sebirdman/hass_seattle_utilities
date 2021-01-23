"""Sensor platform for integration_blueprint."""
from .const import DEFAULT_NAME, DOMAIN, ICON, SENSOR
from .entity import IntegrationBlueprintEntity

async def async_setup_entry(hass, entry, async_add_devices):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    for meter in coordinator.data:
      async_add_devices([KWHSensor(coordinator, entry, meter)])

class KWHSensor(IntegrationBlueprintEntity):
    """Seattle Utility KWH Sensor class."""

    def __init__(self, coordinator, entry, meter_id):
      super().__init__(coordinator, entry)
      self.meter_id = meter_id

    @property
    def unique_id(self):
        return f"{self.meter_id}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.meter_id} SCL"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.meter_id]

    @property
    def unit_of_measurement(self):
        return "kWh"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON
