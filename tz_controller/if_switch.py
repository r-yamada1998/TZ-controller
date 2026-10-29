       
from .device_base import DeviceBase

class IFSwitch(DeviceBase):
    Manufacturer = "Agilent"
    Model = "11713B"
    Identifier = "host"

    def __init__(self, device_name, config_file) -> None:
        super().__init__(device_name, config_file)
        import ogameasure

        com = ogameasure.gpib_prologix(self.device_config.host, self.device_config.port)
        self.sw = ogameasure.Agilent.agilent_11713B(com)

    def open(self, channel):
        self.sw.switch_open(channel)
        return None
    
    def close(self, channel):
        self.sw.switch_open(channel)

    def setup(self,**kwargs):
        if "oc" in kwargs:
            self.oc = kwargs["oc"]

        if "channel" in kwargs:
            self.channel = kwargs["channel"]

    def run(self):

        if self.oc == "open":
            self.open(self.channel)
        
        if self.oc == "close":
            self.close(self.channel)

    def teardown(self):
        pass

    def query(self, command):
        """
        Send a query and return the answer, e.g.
            query(":DIAGnostic:RELay:CYCles? (@105,106,107,108)")
        The relay cycle counters show whether a path was really driven: the
        open and close commands get no answer of their own.

        A read that times out leaves the connection unreadable, so the
        connection is opened again and SYST:ERR? asked; the error is raised
        with that answer.
        """
        com = self.sw.com
        try:
            com.send(command)
            return com.readline().strip()
        except Exception as e:
            self._reconnect()
            try:
                com.send("SYST:ERR?")
                err = com.readline().strip()
            except Exception:
                self._reconnect()
                err = "no answer either"
            raise TimeoutError(f"No answer to {command!r} ({e}); SYST:ERR? -> {err}") from e

    def _reconnect(self):
        com = self.sw.com
        try:
            com.close()
        except Exception:
            pass
        com.open()
