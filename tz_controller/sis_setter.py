from .device_base import DeviceBase

class SISSetter(DeviceBase):

    Manufacturer = "Interface"
    Model = "CPZ3346A"
    Identifier = "rsw_id"

    def __init__(self, device_name, config_file) -> None:
        super().__init__(device_name, config_file)
        
        import pyinterface
        self.da = pyinterface.open(3346,self.device_config.rsw_id)
        self.da.initialize()

    def setup(self):
        self.ch_list = self.device_config.ch_num_li
        self.ch_range = self.device_config.ch_range
        if isinstance(self.ch_range, list):
            if len(self.ch_range) != len(self.ch_list):
                raise ValueError("length of ch_range does not match the length of ch_list")
            self.metadata_dict = dict(zip(self.ch_list, self.ch_range))
        elif isinstance(self.ch_range, str):
            self.metadata_dict = {ch: self.ch_range for ch in self.ch_list}
        else:
            raise TypeError("ch_range must be string")

    def run(self, **kwargs):
        self.da.da.output_da(self.metadata_dict, **kwargs)
        return None
    
    def teardown(self):
        self.da.output_da(self.metadata_dict, [0] * len(self.metadata_dict))
