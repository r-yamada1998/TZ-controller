import time
from .device_base import DeviceBase


class LoAttenuator(DeviceBase):
    """
    Controller for local attenuators defined in device_config.toml.

    Expected TOML structure:

        [local_attenuator]
        _ = "GPVDC15"
        host = "192.168.223.102"

        [local_attenuator.channels]
        4 = { att_current = 10.0 }
        5 = { att_current = 12.5 }
    """

    Manufacturer = "ELVA1"
    Model = "GPVDC15"
    Identifier = "host"

    def __init__(self, device_name: str, config_file: str, lock_dir: str = "/tmp") -> None:
        super().__init__(device_name=device_name, config_file=config_file, lock_dir=lock_dir)

        import ogameasure

        self.ogameasure = ogameasure
        self.loatts: dict[int, object] = {}
        self.att_current_map: dict[int, float | None] = {}

        self.target_ports: list[int] = []
        self.resolved_att_current_map: dict[int, float | None] = {}

        host = self.device_config.host
        channels = getattr(self.device_config, "channels", {})

        for gpib_port_raw, ch_cfg in channels.items():
            gpib_port = int(gpib_port_raw)

            com = self.ogameasure.gpib_prologix(host, gpib_port)
            lo = self.ogameasure.ELVA1.GPDVC15.GPDVC15_100(com)
            lo.com.close()

            self.loatts[gpib_port] = lo
            self.att_current_map[gpib_port] = getattr(ch_cfg, "att_current", None)

            time.sleep(0.5)

    def _normalize_ports(self, gpib_port=None) -> list[int]:
        """
        Normalize gpib_port input into a list of integer ports.

        Parameters
        ----------
        gpib_port : int | list[int] | tuple[int] | set[int] | None
            Target GPIB port(s). If None, all configured ports are used.

        Returns
        -------
        list[int]
            Normalized list of target ports.
        """
        if gpib_port is None:
            return list(self.loatts.keys())

        if isinstance(gpib_port, (list, tuple, set)):
            ports = [int(port) for port in gpib_port]
        else:
            ports = [int(gpib_port)]

        unknown_ports = [port for port in ports if port not in self.loatts]
        if unknown_ports:
            raise KeyError(f"Undefined gpib_port(s): {unknown_ports}")

        return ports

    def _resolve_att_current_map(self, gpib_port=None, att_current=None) -> dict[int, float | None]:
        """
        Resolve attenuation currents for each configured port.

        Resolution rule
        ---------------
        1. Start from values in config.
        2. Override with kwargs if provided.

        Accepted forms
        --------------
        - att_current={4: 10.0, 5: 12.5}
        - gpib_port=4, att_current=10.0
        - gpib_port=[4, 5], att_current=10.0
        - no kwargs -> use config values

        Parameters
        ----------
        gpib_port : int | list[int] | tuple[int] | set[int] | None
            Target port(s) when att_current is a scalar.
        att_current : float | dict[int, float] | None
            Override attenuation current(s).

        Returns
        -------
        dict[int, float | None]
            Resolved map of port to attenuation current.
        """
        resolved = dict(self.att_current_map)

        if att_current is None:
            return resolved

        if isinstance(att_current, dict):
            for port, value in att_current.items():
                port = int(port)
                if port not in self.loatts:
                    raise KeyError(f"Undefined gpib_port={port}")
                resolved[port] = value
            return resolved

        ports = self._normalize_ports(gpib_port)
        for port in ports:
            resolved[port] = att_current

        return resolved

    def setup(self, **kwargs) -> None:
        """
        Resolve target ports and attenuation currents without touching hardware.

        Keyword Arguments
        -----------------
        gpib_port : int | list[int] | tuple[int] | set[int], optional
            Target GPIB port(s). If omitted, all configured ports are targeted.
        att_current : float | dict[int, float], optional
            Override attenuation current(s). If omitted, config values are used.
        """
        gpib_port = kwargs.get("gpib_port")
        att_current = kwargs.get("att_current")

        self.target_ports = self._normalize_ports(gpib_port)
        self.resolved_att_current_map = self._resolve_att_current_map(
            gpib_port=gpib_port,
            att_current=att_current,
        )

        for port in self.target_ports:
            value = self.resolved_att_current_map.get(port)
            self.logger.info(
                "Resolved local attenuator setting: gpib_port=%s, att_current=%s",
                port,
                value,
            )

    def run(self) -> None:
        """
        Apply the resolved attenuation current settings to the hardware.

        Notes
        -----
        This method assumes setup() has already been called.
        """
        if not self.target_ports:
            self.setup()

        for port in self.target_ports:
            if port not in self.resolved_att_current_map:
                raise ValueError(f"att_current is not defined for gpib_port={port}")

            att_current = self.resolved_att_current_map[port]
            if att_current is None:
                raise ValueError(f"att_current is not defined for gpib_port={port}")

            lo = self.loatts[port]

            lo.com.open()
            try:
                lo.output_set(att_current)
                self.logger.info(
                    "Set local attenuator: gpib_port=%s, att_current=%s",
                    port,
                    att_current,
                )
            finally:
                lo.com.close()

    def teardown(self) -> None:
        """
        Clear resolved runtime state.
        """
        self.target_ports = []
        self.resolved_att_current_map = {}