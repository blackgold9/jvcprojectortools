"""Compatibility layer for JVC Projector binary commands."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Final

from jvcprojector import command
from jvcprojector.device import (
    Device,
    HEAD_OP,
    HEAD_REF,
    HEAD_RES,
    HEAD_ACK,
    UNIT_ID,
    END,
    HEAD_LEN,
    JvcProjectorReadWriteTimeoutError,
    JvcProjectorError,
)
from jvcprojector.projector import JvcProjector

_LOGGER = logging.getLogger(__name__)


class BinarySupportedDevice(Device):
    """Device class with support for binary data transmission and raw commands."""

    async def send_binary(self, command_code: str, data: bytes) -> None:
        """Send a binary command to the device.

        Protocol:
        1. Send Command (OP header + code)
        2. Receive ACK
        3. Send Raw Data
        4. Receive ACK
        """
        async with self._lock:
            if self._keepalive:
                self._keepalive.cancel()
                self._keepalive = None

            # 1. Send Command
            if not self._conn.is_connected():
                await self._connect()

            # Construct Operation Command
            cmd_packet = HEAD_OP + command_code.encode() + END

            _LOGGER.debug("Sending binary op header: %s", cmd_packet)
            await self._conn.write(cmd_packet)

            # 2. Receive First ACK
            # The ACK format is usually HEAD_ACK + CODE
            expected_ack_start = HEAD_ACK + command_code.encode()[0:2]

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

    async def exec_raw_op(self, command_code: str, value: str = "") -> None:
        """Execute a raw operation command (non-binary)."""
        async with self._lock:
            if self._keepalive:
                self._keepalive.cancel()
                self._keepalive = None

            if not self._conn.is_connected():
                await self._connect()

            cmd_bytes = command_code.encode()
            val_bytes = value.encode() if value else b""

            # Construct: ! + UNIT_ID + CODE + VALUE + END
            cmd_packet = HEAD_OP + cmd_bytes + val_bytes + END

            _LOGGER.debug("Sending raw op: %s", cmd_packet)
            await self._conn.write(cmd_packet)

            expected_ack_start = HEAD_ACK + cmd_bytes[0:2]

            try:
                ack_data = await self._conn.readline(timeout=5.0)
            except asyncio.TimeoutError as e:
                raise JvcProjectorReadWriteTimeoutError(
                    f"Read timeout waiting for ACK for raw command {command_code}"
                ) from e

            if not ack_data.startswith(expected_ack_start):
                 raise JvcProjectorError(
                    f"Invalid ack '{ack_data!r}' for raw command {command_code}"
                )

            _LOGGER.debug("Received ack: %s", ack_data)

    async def exec_raw_ref(self, command_code: str) -> bytes:
        """Execute a raw reference command and return response body bytes."""
        async with self._lock:
            if self._keepalive:
                self._keepalive.cancel()
                self._keepalive = None

            if not self._conn.is_connected():
                await self._connect()

            cmd_bytes = command_code.encode()

            # Construct: ? + UNIT_ID + CODE + END
            cmd_packet = HEAD_REF + cmd_bytes + END

            _LOGGER.debug("Sending raw ref: %s", cmd_packet)
            await self._conn.write(cmd_packet)

            expected_ack_start = HEAD_ACK + cmd_bytes[0:2]
            expected_res_start = HEAD_RES + cmd_bytes[0:2]

            # 1. Receive ACK
            try:
                ack_data = await self._conn.readline(timeout=5.0)
            except asyncio.TimeoutError as e:
                raise JvcProjectorReadWriteTimeoutError(
                    f"Read timeout waiting for ACK for raw ref {command_code}"
                ) from e

            if not ack_data.startswith(expected_ack_start):
                 raise JvcProjectorError(
                    f"Invalid ack '{ack_data!r}' for raw ref {command_code}"
                )

            _LOGGER.debug("Received ack: %s", ack_data)

            # 2. Receive Response
            try:
                res_data = await self._conn.readline(timeout=5.0)
            except asyncio.TimeoutError as e:
                raise JvcProjectorReadWriteTimeoutError(
                    f"Read timeout waiting for response for raw ref {command_code}"
                ) from e

            _LOGGER.debug("Received raw response: %s", res_data)

            if not res_data.startswith(expected_res_start):
                 raise JvcProjectorError(
                    f"Invalid response header '{res_data!r}' for raw ref {command_code}"
                )

            # Extract bytes value
            # DEBUG
            # print(f"DEBUG: HEAD_LEN={HEAD_LEN}, res_data={res_data}, slice_start={HEAD_LEN + 2}")
            value_bytes = res_data[HEAD_LEN + 2 : -1]
            return value_bytes

    async def exec_raw_ref_binary(self, command_code: str) -> bytes:
        """Execute a raw reference command for binary data retrieval."""
        async with self._lock:
            if self._keepalive:
                self._keepalive.cancel()
                self._keepalive = None

            if not self._conn.is_connected():
                await self._connect()

            cmd_bytes = command_code.encode()

            # Construct: ? + UNIT_ID + CODE + END
            cmd_packet = HEAD_REF + cmd_bytes + END

            _LOGGER.debug("Sending raw ref binary: %s", cmd_packet)
            await self._conn.write(cmd_packet)

            expected_ack_start = HEAD_ACK + cmd_bytes[0:2]

            # 1. Receive ACK
            try:
                ack_data = await self._conn.readline(timeout=5.0)
            except asyncio.TimeoutError as e:
                raise JvcProjectorReadWriteTimeoutError(
                    f"Read timeout waiting for ACK for raw ref binary {command_code}"
                ) from e

            if not ack_data.startswith(expected_ack_start):
                 raise JvcProjectorError(
                    f"Invalid ack '{ack_data!r}' for raw ref binary {command_code}"
                )

            _LOGGER.debug("Received ack: %s", ack_data)

            # 2. Receive Binary Data (no readline, just read)
            try:
                # Read up to 1024 bytes as per old protocol logic
                data = await self._conn.read(1024)
            except asyncio.TimeoutError as e:
                raise JvcProjectorReadWriteTimeoutError(
                    f"Read timeout waiting for binary data for {command_code}"
                ) from e

            if not data:
                 raise JvcProjectorReadWriteTimeoutError("Connection closed or empty response")

            _LOGGER.debug("Received binary data (%d bytes)", len(data))
            return data


class BinarySupportedJvcProjector(JvcProjector):
    """JVC Projector with binary command support."""

    async def connect(self, *, model: str | None = None) -> None:
        """Initialize communication with the projector using BinarySupportedDevice."""
        if self._device:
            return

        self._device = BinarySupportedDevice(
            self._host, self._port, self._timeout, self._password
        )

        self._model = model if model else await self.get(command.ModelName)

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
        if not isinstance(self._device, BinarySupportedDevice):
             raise JvcProjectorError("Device does not support binary commands")
        await self._device.send_binary(command_code, data)

    async def raw_set(self, command_code: str, value: str = "") -> None:
        """Send a raw operation command."""
        if not self._device:
            raise JvcProjectorError("Not connected")
        if not isinstance(self._device, BinarySupportedDevice):
             raise JvcProjectorError("Device does not support raw commands")
        await self._device.exec_raw_op(command_code, value)

    async def raw_get(self, command_code: str) -> bytes:
        """Send a raw reference command and get raw response bytes."""
        if not self._device:
            raise JvcProjectorError("Not connected")
        if not isinstance(self._device, BinarySupportedDevice):
             raise JvcProjectorError("Device does not support raw commands")
        return await self._device.exec_raw_ref(command_code)

    async def raw_get_binary(self, command_code: str) -> bytes:
        """Send a raw reference command and get binary response bytes."""
        if not self._device:
            raise JvcProjectorError("Not connected")
        if not isinstance(self._device, BinarySupportedDevice):
             raise JvcProjectorError("Device does not support raw commands")
        return await self._device.exec_raw_ref_binary(command_code)
