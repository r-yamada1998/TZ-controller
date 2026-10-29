from __future__ import annotations

import time
from typing import Any, Dict

from .device_base import DeviceBase


class IrrSignalGenerator(DeviceBase):
    """
    Phase Matrix FSW-0020, the test signal source for IRR measurement.

    Config example (device_config.toml):
        [irr_signal_generator]
        _ = "FSW0020"
        host = "192.168.223.101"
        port = 10001

    Usage:
        sg.setup(freq=14.609, output=True)   # GHz; the receiver sees x6
        sg.run()
        sg.teardown()                        # output off, connection closed
        sg.close()                           # connection closed, output kept

    The generator does not answer queries, so nothing is read back.
    """

    Manufacturer = "Phase Matrix"
    Model = "FSW-0020"
    Identifier = "host"

    # The generator drops a command that follows the previous one at once
    # (output on right after a frequency change gave no signal).
    COMMAND_GAP = 1.0  # s

    def __init__(self, device_name: str, config_file: str) -> None:
        super().__init__(device_name, config_file)

        import ogameasure

        self.com = ogameasure.ethernet(self.device_config.host, int(self.device_config.port))
        self.com.open()
        self.sg = ogameasure.Phasematrix.FSW0020(self.com)
        self.sg.use_external_reference_source()

        self.pending: Dict[str, Any] = {}

    def setup(self, **kwargs: Any) -> None:
        """
        freq    [GHz], or None to leave it
        output  True / False, or None to leave it
        """
        freq = kwargs.get("freq")
        output = kwargs.get("output")
        if freq is not None and not isinstance(freq, (int, float)):
            raise TypeError("freq must be int or float")
        if output is not None and not isinstance(output, bool):
            raise TypeError("output must be bool")
        self.pending = {"freq": freq, "output": output}

    def run(self) -> None:
        if not self.pending:
            raise RuntimeError("setup() must be called before run().")
        p = self.pending
        if p["freq"] is not None:
            self.sg.freq_set(float(p["freq"]), "GHz")
            time.sleep(self.COMMAND_GAP)
        if p["output"] is not None:
            self.sg.output_set(1 if p["output"] else 0)
            time.sleep(self.COMMAND_GAP)

    def teardown(self) -> None:
        """Output off, then close the connection."""
        try:
            self.sg.output_set(0)
            time.sleep(self.COMMAND_GAP)
        finally:
            self.close()

    def close(self) -> None:
        """Close the connection and leave the output as it is."""
        self.com.close()
