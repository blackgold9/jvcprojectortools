DOMAIN = 'jvc_projector'

IP_ADDRESS = '192.168.86.44'
import jvc_command
import logging
import voluptuous as vol
import homeassistant.helpers.entity.ToggleEntity

from jvc_command import(
    JVCCommand, CommandNack, Command, HDMIInputLevel, PictureMode, PowerState, RemoteCode,
    GammaTable, GammaCorrection, LowLatency)

def setup(hass, config):
  """Set up the JVC Projector component"""
  self.jvc = JVCCommand(host=IP_ADDRESS)

  

class JVCProjector(ToggleEntity)
def update(self):
	with self.jvc as cmd:
		self._powerState = cmd.get(Command.Power)
		self._lowLatencyState = None
		if (self._powerState == PowerState.LampOn):
		  self._lowLatencyState = cmd.get(Command.LowLatency)

