import time
from .device_base import DeviceBase


class LoAttenuator(DeviceBase):
    def __init__(self, device_name, config_file) -> None:
        """
        Initialize the LO attenuator instances from the configuration file.

        The configuration is expected to have the following structure:

            [local_attenuator]
            _ = "GPVDC15"
            host = "192.168.223.102"

            [local_attenuator.channels]
            4 = { att_current = 10.0 }
            5 = { att_current = 12.5 }

        Each channel entry maps a GPIB port to its default attenuation current.
        """
        super().__init__(device_name, config_file)
        import ogameasure

        self.loatts = {}
        self.att_current_map = {}
        self.resolved_att_current_map = {}

        channels = self.device_config.get("channels", {})
        host = self.device_config["host"]

        for gpib_port_str, ch_cfg in channels.items():
            gpib_port = int(gpib_port_str)

            com = ogameasure.gpib_prologix(host, gpib_port)
            lo = ogameasure.ELVA1.GPDVC15.GPDVC15_100(com)
            lo.com.close()

            self.loatts[gpib_port] = lo
            self.att_current_map[gpib_port] = ch_cfg.get("att_current")

            time.sleep(5)

    def _resolve_att_current_map(self, **kwargs) -> dict:
        """
        Resolve the attenuation current map.

        Keyword Arguments
        -----------------
        gpib_port : int | list[int] | tuple[int] | set[int], optional
            Target GPIB port or ports.
        att_current : float | dict[int, float], optional
            Override value(s) for attenuation current.

        Returns
        -------
        dict
            A dictionary mapping GPIB ports to resolved attenuation currents.

        Notes
        -----
        The resolution rule is:
        1. Use values provided via kwargs if present.
        2. Otherwise, use values from the configuration file.

        Accepted forms:
            - att_current={4: 10.0, 5: 12.5}
            - gpib_port=4, att_current=10.0
            - no kwargs -> use configuration values
        """
        resolved = dict(self.att_current_map)

        if "att_current" not in kwargs:
            return resolved

        att_current = kwargs["att_current"]

        if isinstance(att_current, dict):
            for port, value in att_current.items():
                resolved[int(port)] = value
            return resolved

        if "gpib_port" in kwargs:
            gpib_port = kwargs["gpib_port"]

            if isinstance(gpib_port, (list, tuple, set)):
                for port in gpib_port:
                    resolved[int(port)] = att_current
            else:
                resolved[int(gpib_port)] = att_current

            return resolved

        raise ValueError(
            "If att_current is given as a scalar, gpib_port must also be specified."
        )

    def _resolve_targets(self, **kwargs) -> dict:
        """
        Resolve target attenuator instances.

        Keyword Arguments
        -----------------
        gpib_port : int | list[int] | tuple[int] | set[int], optional
            Target GPIB port or ports.

        Returns
        -------
        dict
            A dictionary mapping target GPIB ports to attenuator instances.

        Notes
        -----
        If gpib_port is not specified, all configured attenuators are returned.
        """
        if "gpib_port" not in kwargs:
            return dict(self.loatts)

        gpib_port = kwargs["gpib_port"]

        if isinstance(gpib_port, (list, tuple, set)):
            return {int(port): self.loatts[int(port)] for port in gpib_port}

        gpib_port = int(gpib_port)
        return {gpib_port: self.loatts[gpib_port]}

    def setup(self, **kwargs) -> None:
        """
        Resolve and store attenuation current values without touching hardware.

        Keyword Arguments
        -----------------
        gpib_port : int | list[int] | tuple[int] | set[int], optional
            Target GPIB port or ports for scalar override.
        att_current : float | dict[int, float], optional
            Override value(s) for attenuation current.

        Notes
        -----
        This method only prepares the values to be used later by run().
        No hardware communication is performed here.
        """
        self.resolved_att_current_map = self._resolve_att_current_map(**kwargs)

        for port, value in self.resolved_att_current_map.items():
            self.logger.info(
                f"Resolved att_current: gpib_port={port}, att_current={value}"
            )

    def run(self, **kwargs) -> None:
        """
        Apply attenuation current settings to the hardware.

        Keyword Arguments
        -----------------
        gpib_port : int | list[int] | tuple[int] | set[int], optional
            Target GPIB port or ports.
        att_current : float | dict[int, float], optional
            Override value(s) for attenuation current.

        Notes
        -----
        If kwargs are provided, they are resolved at runtime.
        Otherwise, this method uses the values already prepared by setup().

        Hardware access is performed only in this method.
        """
        targets = self._resolve_targets(**kwargs)

        if kwargs:
            resolved_map = self._resolve_att_current_map(**kwargs)
        else:
            if not self.resolved_att_current_map:
                self.resolved_att_current_map = self._resolve_att_current_map()
            resolved_map = self.resolved_att_current_map

        for port, lo in targets.items():
            if port not in resolved_map:
                raise ValueError(f"att_current is not defined for gpib_port={port}")

            att_current = resolved_map[port]

            lo.com.open()
            try:
                lo.output_set()
                lo.current_set(att_current)
                self.logger.info(
                    f"Set LO attenuator: gpib_port={port}, att_current={att_current}"
                )
            finally:
                lo.com.close()


