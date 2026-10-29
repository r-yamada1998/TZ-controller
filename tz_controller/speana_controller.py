from __future__ import annotations

import time
from typing import Any, ClassVar, Optional, Union

import numpy as np

from .configuration import Config
from .device_base import DeviceBase


class SpectrumAnalyzer(DeviceBase):
    """
    Device controller for the Keysight N9343C spectrum analyzer.

    Updated behavior:
        - setup(**kwargs): resolve parameters and apply them to hardware
        - run(): query and return trace data only
        - teardown(): optional cleanup

    Configuration example:

        [spectrum_analyzer]
        _ = "KeysightN9343C"
        host = "192.168.223.105"
        port = 5025

        [spectrum_analyzer.defaults]
        center = "6GHz"
        span = "0MHz"
        rbw = "300Hz"
        vbw = "300Hz"
        scale_type = "LOG"
        average_onoff = "OFF"

    Optional connection settings:

        timeout = 15      # s to wait for an answer (ogameasure default: 3)
        keep_open = true  # open the connection once and keep it

    On a new connection the N9343C answers the first query after about 4 s
    (measured 2026-10-22), so with the default 3 s every call that opens a
    new connection times out. keep_open = true opens the connection here,
    once, and keeps it until disconnect(); every call then answers at once.
    """

    Model: ClassVar[str] = "N9343C"
    Manufacturer: ClassVar[str] = "Keysight"
    Identifier: ClassVar[Optional[str]] = "host"
    Config: ClassVar[Union[Config, None]] = None

    def __init__(
        self,
        device_name: str,
        config_file: str,
        lock_dir: str = "/tmp",
    ) -> None:
        """
        Initialize the spectrum analyzer controller from configuration.
        """
        super().__init__(device_name=device_name, config_file=config_file, lock_dir=lock_dir)

        import ogameasure

        self.host = self.device_config.host
        self.port = self.device_config.port
        self.defaults = getattr(self.device_config, "defaults", {})

        self.com = ogameasure.ethernet(self.host, self.port)
        self.sa = ogameasure.Keysight.N9343C(self.com)

        timeout = getattr(self.device_config, "timeout", None)
        if timeout is not None:
            self.com.timeout = float(timeout)
        self.keep_open = bool(getattr(self.device_config, "keep_open", False))
        if self.keep_open:
            self.com.open()

        self._k = 10**3
        self._M = 10**6
        self._G = 10**9

    def setup(self, **kwargs) -> None:
        """
        Resolve parameters from config defaults and kwargs, then apply them to hardware.

        Parameters passed through kwargs override configuration defaults.

        Accepted parameters include:
            center
            start
            stop
            span
            ref_level
            att
            att_auto
            scale_div
            scale_type
            rbw
            rbw_auto
            vbw
            vbw_auto
            average_num
            average_onoff
            average_restart
            sweep_time
            preset_0span
        """
        params = dict(self._config_defaults_as_dict())
        params.update(kwargs)

        self._open()
        try:
            if params.get("preset_0span", False):
                self._apply_0span_preset()

            # The analyzer refuses a wide span while the RBW is still small
            # (2026-10-22). So the bandwidths are sent before the span, and
            # at zero span when the span changes too.
            if any(k in params for k in ("start", "stop", "span")) and any(
                k in params for k in ("rbw", "rbw_auto", "vbw", "vbw_auto")
            ):
                self.sa.frequency_span_set("0Hz")

            if "rbw" in params:
                self.sa.resolution_bw_set(params["rbw"])
                self.logger.info("RBW set to %r", params["rbw"])

            if "rbw_auto" in params:
                self.sa.resolution_bw_auto_set(params["rbw_auto"])
                self.logger.info("RBW auto set to %r", params["rbw_auto"])

            if "vbw" in params:
                self.sa.video_bw_set(params["vbw"])
                self.logger.info("VBW set to %r", params["vbw"])

            if "vbw_auto" in params:
                self.sa.video_bw_auto_set(params["vbw_auto"])
                self.logger.info("VBW auto set to %r", params["vbw_auto"])

            if "center" in params:
                self.sa.frequency_center_set(params["center"])
                self.logger.info("Center frequency set to %r", params["center"])

            if "start" in params:
                self.sa.frequency_start_set(params["start"])
                self.logger.info("Start frequency set to %r", params["start"])

            if "stop" in params:
                self.sa.frequency_stop_set(params["stop"])
                self.logger.info("Stop frequency set to %r", params["stop"])

            if "span" in params:
                self.sa.frequency_span_set(params["span"])
                self.logger.info("Span set to %r", params["span"])

            if "ref_level" in params:
                self.sa.reference_level_set(params["ref_level"])
                self.logger.info("Reference level set to %r dBm", params["ref_level"])

            if "att" in params:
                self.sa.attenuation_set(params["att"])
                self.logger.info("Attenuation set to %r dB", params["att"])

            if "att_auto" in params:
                self.sa.attenuation_auto_set(params["att_auto"])
                self.logger.info("Attenuation auto set to %r", params["att_auto"])

            if "scale_div" in params:
                self.sa.scalediv_set(params["scale_div"])
                self.logger.info("Scale division set to %r", params["scale_div"])

            if "scale_type" in params:
                self.sa.scaletype_set(params["scale_type"])
                self.logger.info("Scale type set to %r", params["scale_type"])

            if "average_num" in params:
                self.sa.average_set(params["average_num"])
                self.logger.info("Average number set to %r", params["average_num"])

            if "average_onoff" in params:
                self.sa.average_onoff_set(params["average_onoff"])
                self.logger.info("Average on/off set to %r", params["average_onoff"])

            if params.get("average_restart", False):
                self.sa.average_restart()
                self.logger.info("Averaging restarted")

            if "sweep_time" in params:
                self.sa.sweep_time_set(params["sweep_time"])
                self.logger.info("Sweep time set to %r s", params["sweep_time"])

        finally:
            self._close()

    def run(self):
        """
        Query and return trace data from the spectrum analyzer.
        """
        self._open()
        try:
            return self.sa.trace_data_query()
        finally:
            self._close()

    def teardown(self) -> None:
        """
        Perform optional cleanup after run().

        No hardware action is required here because communication is opened and
        closed inside each hardware-accessing method (or kept, see keep_open).
        """
        pass

    def disconnect(self) -> None:
        """Close the connection kept open by keep_open."""
        if self.keep_open:
            self.com.close()

    def sweep_time(self) -> float:
        """Sweep time [s] as the analyzer reports it."""
        self._open()
        try:
            return float(self.sa.sweep_time_query())
        finally:
            self._close()

    def fresh_trace(self, average_num: int) -> Any:
        """
        Restart the averaging, wait until average_num sweeps are done, and
        return the trace. Nothing from before the call (IF band, load, test
        signal) is in it; the TZ manual asks the operator to confirm the
        averaging has completed before recording. Call it after the wait for
        the receiver to settle.
        """
        self._open()
        try:
            self.sa.average_restart()
            sweep = float(self.sa.sweep_time_query())
        finally:
            self._close()
        wait = average_num * sweep * 1.2 + 1.0
        self.logger.info("Waiting %.1f s for %d averaged sweeps", wait, average_num)
        time.sleep(wait)
        return self.run()

    def set_continuous(self, on: bool) -> None:
        """Continuous sweep on or off (INIT:CONT). On is the usual state."""
        self._open()
        try:
            self.com.send("INIT:CONT " + ("ON" if on else "OFF"))
        finally:
            self._close()

    def single_trace(self) -> Any:
        """
        Start one sweep, wait until the analyzer reports it finished, and
        return the trace: a trace that surely comes from a sweep started by
        this call. Needs set_continuous(False).
        """
        self._open()
        try:
            self.com.send("INIT:IMM;*OPC?")
            self.com.readline()
            return self.sa.trace_data_query()
        finally:
            self._close()

    def _open(self) -> None:
        if not self.keep_open:
            self.com.open()

    def _close(self) -> None:
        if not self.keep_open:
            self.com.close()

    def _config_defaults_as_dict(self) -> dict[str, Any]:
        """
        Convert configuration defaults into a plain dictionary.
        """
        defaults = self.defaults

        if defaults is None:
            return {}

        if isinstance(defaults, dict):
            return dict(defaults)

        try:
            return dict(defaults.items())
        except Exception:
            try:
                return dict(vars(defaults))
            except Exception:
                return {}

    def _apply_0span_preset(self) -> None:
        """
        Apply the standard 0-span preset to hardware.
        """
        self.sa.frequency_span_set("0MHz")
        self.sa.frequency_center_set("6GHz")
        self.sa.resolution_bw_set("300Hz")
        self.sa.video_bw_set("300Hz")
        self.sa.scaletype_set("LOG")
        self.sa.average_onoff_set("OFF")

        self.logger.info("Applied 0-span preset")

    def get_current_param(self) -> dict[str, Any]:
        """
        Query the current instrument parameters from hardware.
        """
        self._open()
        try:
            result = {
                "center": self.sa.frequency_center_query(),
                "start": self.sa.frequency_start_query(),
                "stop": self.sa.frequency_stop_query(),
                "span": self.sa.frequency_span_query(),
                "ref_level": self.sa.reference_level_query(),
                "att": self.sa.attenuation_query(),
                "att_auto": self.sa.attenuation_auto_query(),
                "scale_div": self.sa.scalediv_query(),
                "scale_type": self.sa.scaletype_query(),
                "rbw": self.sa.resolution_bw_query(),
                "rbw_auto": self.sa.resolution_bw_auto_query(),
                "vbw": self.sa.video_bw_query(),
                "vbw_auto": self.sa.video_bw_auto_query(),
                "average_num": self.sa.average_query(),
                "average_onoff": self.sa.average_onoff_query(),
                "sweep_time": self.sa.sweep_time_query(),
            }
        finally:
            self._close()

        return result

    def print_current_param(self) -> None:
        """
        Query and print the current instrument parameters.
        """
        p = self.get_current_param()

        print()
        print("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=")
        print(f"Center freq. = {p['center'] / self._M} MHz")
        print(f"Start freq. = {p['start'] / self._M} MHz")
        print(f"Stop freq. = {p['stop'] / self._M} MHz")
        print(f"Freq. span = {p['span'] / self._M} MHz")
        print(f"Ref level = {p['ref_level']} dBm")
        print(f"Attenuation = {p['att']} dB")
        print(f"Att auto = {self.auto_set_query(p['att_auto'])}")
        print(f"Scale type = {p['scale_type']}")

        if p["scale_type"] == "LOG":
            scale_unit = " dB"
        elif p["scale_type"] == "LIN":
            scale_unit = " mW"
        else:
            scale_unit = ""

        print(f"Scale div = {p['scale_div']}{scale_unit}")
        print(f"RBW = {p['rbw'] / self._k} kHz")
        print(f"RBW auto = {self.auto_set_query(p['rbw_auto'])}")
        print(f"VBW = {p['vbw'] / self._k} kHz")
        print(f"VBW auto = {self.auto_set_query(p['vbw_auto'])}")
        print(f"Average num = {p['average_num']}")
        print(f"Average onoff = {self.auto_set_query(p['average_onoff'])}")
        print(f"Sweep time = {p['sweep_time']} sec.")
        print("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=")

    def gen_xaxis(self):
        """
        Generate frequency axis and return (x, y) spectrum data.
        """
        self._open()
        try:
            start = self.sa.frequency_start_query()
            stop = self.sa.frequency_stop_query()
            y = self.sa.trace_data_query()
        finally:
            self._close()

        x = np.linspace(start, stop, len(y))

        return x, y

    @staticmethod
    def auto_set_query(query: int) -> str:
        """
        Convert an integer auto-setting response to a readable string.
        """
        if query == 1:
            return "ON"
        if query == 0:
            return "OFF"
        return str(query)