# TZ-controller

This is the Python implementation of the TZ receiver, a part of HINOTORI installed on the Nobeyama 45-m telescope.


## Usage
TZ制御用FACにて実行する。

sshログインののち、
```shell
# cd tz_workspace
# uv run ipython
```

uvでpythonを起動したら、

```python
$ from tz_controller.sis_setter import SISSetter
$ from tz_controller.loatt import LoAttenuator
$ from tz_controller.signal_generator import SignalGenerator

$ loatt = LoAttenuator(device_name="local_attenuator", config_file="device_config.toml")
$ sg = SignalGenerator(device_name="signal_generator", config_file="device_config.toml")
$ sis = SISSetter(device_name="sis_bias_setter", config_file="device_config.toml")
$ loatt.setup()
$ loatt.run()
$ sg.setup()
$ sg.run()
$ sis.setup()
$ sis.run()
```
