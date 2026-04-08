from __future__ import annotations

from typing import Any, Dict

import ogameasure

from .device_base import DeviceBase


class SignalGenerator(DeviceBase):
    """
    APSYN420 controller via ogameasure.

    Design policy:
        - RF mode is fixed to CW
        - External reference is used by default
        - RF output default is ON
        - teardown() ensures RF OFF and connection close
    """

    Manufacturer = "AnaPico"
    Model = "APSYN420"
    Identifier = "host"

    VALID_FREQ_UNITS = {"GHz", "MHz", "kHz", "Hz"}
    VALID_REF_SOURCES = {"INT", "EXT", "SLAV"}

    def __init__(self, device_name: str, config_file: str) -> None:
        super().__init__(device_name, config_file)

        host = self.device_config.host
        port = int(getattr(self.device_config, "port", 18))

        self.com = ogameasure.ethernet(host, port)
        self.com.open()
        self.sg = ogameasure.AnaPico.APSYN420(self.com)

        self.pending: Dict[str, Any] = {}

    # ============================================================
    # setup
    # ============================================================
    def setup(self, **kwargs: Any) -> None:
        defaults = dict(getattr(self.device_config, "defaults", {}))
        reference = dict(getattr(self.device_config, "reference", {}))

        resolved: Dict[str, Any] = {
            "freq": kwargs.get("freq", defaults.get("freq")),
            "freq_unit": kwargs.get("freq_unit", defaults.get("freq_unit", "GHz")),
            "power": kwargs.get("power", defaults.get("power")),
            "output": kwargs.get("output", defaults.get("output")),
            "ref_source": kwargs.get("ref_source", reference.get("source")),
            "ref_ext_freq": kwargs.get("ref_ext_freq", reference.get("ext_freq")),
            "ref_output": kwargs.get("ref_output", reference.get("output")),
        }

        self._validate(resolved)
        self.pending = resolved

    # ============================================================
    # run
    # ============================================================
    def run(self) -> None:
        if not self.pending:
            raise RuntimeError("setup() must be called before run().")

        p = self.pending

        # RF mode (fixed)
        self.sg.rf_mode_set("CW")

        # Reference
        if p["ref_source"] is not None:
            self.sg.ref_source_set(p["ref_source"])

        if p["ref_ext_freq"] is not None:
            self.sg.ref_ext_freq_set(float(p["ref_ext_freq"]))

        if p["ref_output"] is not None:
            if p["ref_output"]:
                self.sg.ref_output_on()
            else:
                self.sg.ref_output_off()

        # Frequency / Power
        if p["freq"] is not None:
            self.sg.freq_set(float(p["freq"]), p["freq_unit"])

        if p["power"] is not None:
            self.sg.power_set(float(p["power"]))

        # RF Output
        if p["output"] is not None:
            if p["output"]:
                self.sg.output_on()
            else:
                self.sg.output_off()

    # ============================================================
    # teardown (安全終了)
    # ============================================================
    def teardown(self) -> None:
        """
        Safe shutdown:
            - RF OFF
            - Close connection
        """
        try:
            self.sg.output_off()
        except Exception as e:
            self.logger.warning("Failed to turn RF OFF: %s", e)

        try:
            self.sg.close()
        except Exception as e:
            self.logger.warning("Failed to close SG connection: %s", e)

    # ============================================================
    # status
    # ============================================================
    def status(self) -> Dict[str, Any]:
        return {
            "freq_hz": self.sg.freq_query(),
            "power_dbm": self.sg.power_query(),
            "output": bool(self.sg.output_query()),
            "ref_source": self.sg.ref_source_query(),
            "ref_output": bool(self.sg.ref_output_query()),
            "ref_locked": bool(self.sg.ref_locked_query()),
        }

    # ============================================================
    # quick API
    # ============================================================
    def set_output_only(self, output: bool) -> None:
        if output:
            self.sg.output_on()
        else:
            self.sg.output_off()

    # ============================================================
    # validation
    # ============================================================
    def _validate(self, p: Dict[str, Any]) -> None:
        if p["freq"] is not None and not isinstance(p["freq"], (int, float)):
            raise TypeError("freq must be int or float")

        if p["freq_unit"] not in self.VALID_FREQ_UNITS:
            raise ValueError(f"invalid freq_unit: {p['freq_unit']}")

        if p["power"] is not None and not isinstance(p["power"], (int, float)):
            raise TypeError("power must be int or float")

        if p["output"] is not None and not isinstance(p["output"], bool):
            raise TypeError("output must be bool")

        if p["ref_source"] not in self.VALID_REF_SOURCES:
            raise ValueError(f"invalid ref_source: {p['ref_source']}")

        if p["ref_ext_freq"] is not None and not isinstance(
            p["ref_ext_freq"], (int, float)
        ):
            raise TypeError("ref_ext_freq must be int or float")

        if p["ref_output"] is not None and not isinstance(p["ref_output"], bool):
            raise TypeError("ref_output must be bool")
