from .device_base import DeviceBase

class SISSetter(DeviceBase):
    def __init__(self, config_file) -> None:
            
        super().__init__(device_name="sis_bias_setter", config_file=config_file)
