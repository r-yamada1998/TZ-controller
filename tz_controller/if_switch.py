       
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
