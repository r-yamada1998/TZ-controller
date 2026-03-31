from .device_base import DeviceBase

class SISSetter(DeviceBase):
    def __init__(self, device_name, config_file) -> None:
        super().__init__(device_name, config_file)
        import pyinterface
        self.ad = pyinterface.open(3177, self.device_config.rsw_id)
        self.ad.stop_sampling()
        self.ad.initialize()

    def setup(self) -> None:
        self.ad.set_sampling_config(smpl_ch_req=self.device_config.smpl_ch_req,
                               smpl_num=self.device_config.smpl_num,
                               smpl_freq=self.device_config.smpl_freq,
                               single_diff=self.device_config.single_diff,
                               trig_mode='ETERNITY'
                               )
        self.ad.start_sampling('ASYNC')

    def run(self, **kwargs) -> None:
        offset = self.ad.get_status()['smpl_count']-self.device_config.ave_num
        data = self.ad.read_sampling_buffer(self.device_config.ave_num, offset)
        data_li_2 = []
        for i in range(self.device_config.all_ch_num):
            data_li = []
            for k in range(self.device_config.ave_num):
                data_li.append(data[k][i])
            data_li_2.append(data_li)

        ave_data_li = []
        for data in data_li_2:
            d = sum(data)/self.device_config.ave_num
            ave_data_li.append(d)
        self.logger.info(f"SIS bias reading results are {ave_data_li}")
        
        