#!/usr/bin/env python3
# author:knakashima
# created: 2026-03-31
# modified: 2026-04-05

from .device_base import DeviceBase
import socket
import time
import ogameasure


class ThermometerController(DeviceBase):
    Manufacturer = "Lakeshore"
    Model = "218"
    Identifier = None       # 温度モニタは一つしかなく区別の必要がないのでNone?

    def __init__(self, device_name, config_file) -> None:
        super().__init__(device_name, config_file)

        host = self.device_config.host
        gpib_port = self.device_config.gpib_port
        self.ch_num = self.device_config.ch_num

        com = ogameasure.gpib_prologix(host, gpib_port)
        self.device = ogameasure.Lakeshore.model218(com)

    # 接続前に特別な初期設定が必要ないのでsetupは定義しない

    def run(self, **kwargs) -> list:
        while True:
            try:
                temps = list(self.device.kelvin_reading_query(ch=0))
                break
            except (socket.timeout, ConnectionResetError, BrokenPipeError):
                self.logger.warning("通信エラー。1秒後に再試行します...")
                time.sleep(1)

        for i in range(self.ch_num):
            self.logger.info(f"CH{i+1}: {temps[i]:.3f} K")

        return temps        # グラフ化や記録のために使うかもしれないので温度のリストを返すことにした。不要ならコメントアウト。
