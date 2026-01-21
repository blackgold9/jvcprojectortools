"""Compatibility layer for JVC Projector binary commands."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Final

from jvcprojector import command
from jvcprojector.device import (
    Device,
    HEAD_OP,
    HEAD_ACK,
    UNIT_ID,
    END,
    JvcProjectorReadWriteTimeoutError,
    JvcProjectorError,
)
from jvcprojector.projector import JvcProjector

_LOGGER = logging.getLogger(__name__)


class BinarySupportedDevice(Device):
    """Device class with support for binary data transmission."""

    async def send_binary(self, command_code: str, data: bytes) -> None:
        """Send a binary command to the device.

        Protocol:
        1. Send Command (OP header + code)
        2. Receive ACK
        3. Send Raw Data
        4. Receive ACK
        """
        # Create a dummy command object just for lock management/throttling logic compatibility if needed,
        # but we'll likely implement the raw send logic here similar to _send.

        # We use the internal lock and connection directly.
        async with self._lock:
            if self._keepalive:
                self._keepalive.cancel()
                self._keepalive = None

            # 1. Send Command
            if not self._conn.is_connected():
                await self._connect()

            # Construct Operation Command
            cmd_packet = HEAD_OP + UNIT_ID + command_code.encode() + END

            _LOGGER.debug("Sending binary op header: %s", cmd_packet)
            await self._conn.write(cmd_packet)

            # 2. Receive First ACK
            # The ACK format is usually HEAD_ACK + UNIT_ID + CODE
            expected_ack_start = HEAD_ACK + UNIT_ID + command_code.encode()[0:2]

            try:
                # Timeout for ACK
                ack_data = await self._conn.readline(timeout=5.0)
            except asyncio.TimeoutError as e:
                raise JvcProjectorReadWriteTimeoutError(
                    f"Read timeout waiting for initial ACK for binary command {command_code}"
                ) from e

            if not ack_data.startswith(expected_ack_start):
                 raise JvcProjectorError(
                    f"Invalid initial ack '{ack_data!r}' for binary command {command_code}"
                )

            _LOGGER.debug("Received initial ack: %s", ack_data)

            # 3. Send Raw Data
            _LOGGER.debug("Sending binary data (%d bytes)", len(data))
            await self._conn.write(data)

            # 4. Receive Second ACK
            try:
                # Timeout for Data ACK might need to be longer
                final_ack = await self._conn.readline(timeout=20.0)
            except asyncio.TimeoutError as e:
                raise JvcProjectorReadWriteTimeoutError(
                    f"Read timeout waiting for data ACK for binary command {command_code}"
                ) from e

            if not final_ack.startswith(expected_ack_start):
                 raise JvcProjectorError(
                    f"Invalid data ack '{final_ack!r}' for binary command {command_code}"
                )

            _LOGGER.debug("Received data ack: %s", final_ack)


class BinarySupportedJvcProjector(JvcProjector):
    """JVC Projector with binary command support."""

    async def connect(self, *, model: str | None = None) -> None:
        """Initialize communication with the projector using BinarySupportedDevice."""
        if self._device:
            return

        # Override the device instantiation to use our subclass
        self._device = BinarySupportedDevice(
            self._host, self._port, self._timeout, self._password
        )

        # The rest is copied from the base class connect method logic
        # We can reuse the base class logic for model detection if we assume self._device is set.
        # However, JvcProjector.connect creates a Device() instance directly.
        # So we basically have to duplicate the logic or call super and then swap?
        # Calling super().connect() would create a standard Device.
        # So we duplicate the init logic here.

        self._model = model if model else await self.get(command.ModelName)

        # Import SPECIFICATIONS locally to avoid circular imports if they exist,
        # or just rely on what we imported from command
        from jvcprojector.command.command import SPECIFICATIONS, Spec
        from jvcprojector.command.base import LIMP_MODE

        self._spec = LIMP_MODE

        for spec in SPECIFICATIONS:
            if spec.matches_model(self._model):
                self._spec = spec
                break

        if self._spec.limp_mode:
            for spec in SPECIFICATIONS:
                if spec.matches_prefix(self._model):
                    msg = "Unknown model %s detected; defaulting %s (%s)"
                    _LOGGER.warning(msg, self._model, spec.model.name, spec.name)
                    self._spec = spec
                    break

        if self._spec.limp_mode:
            _LOGGER.warning(
                "Unknown model %s detected; entering limp mode", self._model
            )

    async def set_binary(self, command_code: str, data: bytes) -> None:
        """Send a binary command."""
        if not self._device:
            raise JvcProjectorError("Not connected")

        # Verify it is our binary device
        if not isinstance(self._device, BinarySupportedDevice):
             raise JvcProjectorError("Device does not support binary commands")

        await self._device.send_binary(command_code, data)
