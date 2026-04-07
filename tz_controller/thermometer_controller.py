#!/usr/bin/env python3
# author:knakashima
# created: 2026-03-31
# modified: 2026-04-05

from .device_base import DeviceBase
import time

class ThermometerController(DeviceBase):
    Manufacturer = "Lakeshore"
    Model = "218"
    Identifier = "host"

    def __init__(self, device_name, config_file) -> None:
        """
        Initialize the ThermometerController from the configuration file.

        The configuration is expected to have the following structure:

            [thermometer_controller]
            _ = "Lakeshore218"
            host = "192.168.100.12"
            gpib_port = 13
            ch_num = 4
        """
        super().__init__(device_name, config_file)
        import ogameasure

        host = self.device_config.host
        gpib_port = self.device_config.gpib_port
        self.ch_num = self.device_config.ch_num

        com = ogameasure.gpib_prologix(host, gpib_port)
        self.device = ogameasure.Lakeshore.model218(com)

    def run(self, **kwargs) -> list | None:
        """
        Acquire temperature readings from all channels.

        Keyword Arguments
        -----------------
        return_data : bool, optional
            If True, return the acquired temperatures.

        Returns
        -------
        list or None
            List of temperatures in Kelvin if return_data=True, otherwise None.
        """
        while True:
            try:
                temps = list(self.device.kelvin_reading_query(ch=0))
                break
            except (socket.timeout, ConnectionResetError, BrokenPipeError):
                self.logger.warning("Connection error. Retrying in 1 second...")
                time.sleep(1)

        for i in range(self.ch_num):
            self.logger.info(f"CH{i+1}: {temps[i]:.3f} K")

        if kwargs.get("return_data"):
            return temps
        return None
