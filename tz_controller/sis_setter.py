from __future__ import annotations

from typing import Dict, List

from .device_base import DeviceBase


class SISSetter(DeviceBase):
    """
    SIS bias setter controller for Interface CPZ3346A.

    Example config:
        [sis_bias_setter]
        _ = "CPZ3346"
        rsw_id = 0
        conversion_factor = 0.3133333333333333
        channel = { v1 = "ch5", h1 = "ch6", h2 = "ch7", v2 = "ch8" }
        range = { v1 = "10V", h1 = "10V", h2 = "10V", v2 = "10V" }
        tuned = { v1 = 6.9, h1 = 6.5, v2 = 6.5, h2 = 7.4 }

    conversion_factor converts a bias command in mV into the DA output voltage
    in volts. It is the calibration of the bias box and MUST be present in
    config: without it a command of 6.9 would put 6.9 V on the DA instead of
    2.16 V, over-biasing the junction by a factor of about 3.2.

    Usage:
        sis.setup(v1=6.9)
        sis.setup(v1=6.9, v2=6.5)
        sis.setup()  # use config.tuned
    """

    Manufacturer = "Interface"
    Model = "CPZ3346A"
    Identifier = "rsw_id"

    VALID_RANGES = {"0_10V", "5V", "10V"}

    def __init__(self, device_name: str, config_file: str) -> None:
        super().__init__(device_name, config_file)

        import pyinterface

        self.da = pyinterface.open(3346, self.device_config.rsw_id)
        self.da.initialize()

        self.smpl_ch_req: List[Dict[str, object]] = []
        self.data: List[float] = []

    def setup(self, **kwargs: float) -> None:
        """
        Resolve output channels, ranges, and voltages from keyword arguments.

        Examples:
            setup(v1=6.9)
            setup(v1=6.9, v2=6.5)

        If no kwargs are given, config.tuned is used.
        """
        channel_map = dict(self.device_config.channel)
        range_map = dict(self.device_config.range)
        tuned_map = dict(self.device_config.tuned)

        requested = kwargs if kwargs else tuned_map

        self.conversion_factor = self._resolve_conversion_factor()

        smpl_ch_req: List[Dict[str, object]] = []
        data: List[float] = []

        for name, value in requested.items():
            if name not in channel_map:
                valid = ", ".join(channel_map.keys())
                raise KeyError(
                    f"Unknown bias name: {name!r}. Valid names are: {valid}"
                )

            if name not in range_map:
                raise KeyError(f"Range is not defined for {name!r} in config.")

            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"Bias value for {name!r} must be int or float, "
                    f"got {type(value).__name__}"
                )

            range_name = range_map[name]
            if range_name not in self.VALID_RANGES:
                valid = ", ".join(sorted(self.VALID_RANGES))
                raise ValueError(
                    f"Invalid range for {name!r}: {range_name!r}. "
                    f"Valid ranges are: {valid}"
                )

            ch_no = self._parse_channel_number(channel_map[name])

            smpl_ch_req.append(
                {
                    "ch_no": ch_no,
                    "range": range_name,
                }
            )
            data.append(float(value)*self.conversion_factor)

        self.smpl_ch_req = smpl_ch_req
        self.data = data

    def run(self) -> None:
        """
        Output resolved voltages to the DA board.
        """
        if not self.smpl_ch_req or not self.data:
            raise RuntimeError("setup() must be called before run().")

        self.da.output_da(self.smpl_ch_req, self.data)

    def teardown(self) -> None:
        """
        Reset only the channels used in the last setup() to 0 V.
        """
        if not self.smpl_ch_req:
            return

        zero_data = [0.0] * len(self.smpl_ch_req)
        self.da.output_da(self.smpl_ch_req, zero_data)

    def _resolve_conversion_factor(self) -> float:
        """
        Read the bias box calibration from config.

        Deliberately has no default. A missing factor would silently apply the
        raw command value to the DA board, which over-biases the junction by
        the box gain (about 3.2 for the current hardware).
        """
        factor = getattr(self.device_config, "conversion_factor", None)

        if factor is None:
            raise KeyError(
                "conversion_factor is not defined for "
                f"{self.device_name!r} in config. It converts a bias command "
                "in mV into the DA output voltage in volts, and there is no "
                "safe default: without it the raw command value would reach "
                "the DA board and over-bias the junction."
            )

        if not isinstance(factor, (int, float)) or isinstance(factor, bool):
            raise TypeError(
                "conversion_factor must be int or float, "
                f"got {type(factor).__name__}"
            )

        return float(factor)

    @staticmethod
    def _parse_channel_number(ch_label: str) -> int:
        """
        Convert a channel label like 'ch5' to integer 5.
        """
        if not isinstance(ch_label, str):
            raise TypeError(
                f"Channel label must be a string like 'ch5', got {type(ch_label).__name__}"
            )

        if not ch_label.startswith("ch"):
            raise ValueError(f"Invalid channel label: {ch_label!r}")

        try:
            return int(ch_label[2:])
        except ValueError as e:
            raise ValueError(f"Invalid channel label: {ch_label!r}") from e
