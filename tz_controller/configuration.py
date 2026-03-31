import tomli
import pathlib
from typing import Union

class Config(dict):
    def __init__(self, *args, **kwargs):
        super().__init__()
        data = dict(*args, **kwargs)
        for key, value in data.items():
            self[key] = self._convert(value)

    def _convert(self, value):
        if isinstance(value, dict):
            return Config(value)
        elif isinstance(value, list):
            return [self._convert(v) for v in value]
        return value

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = self._convert(value)

    def __delattr__(self, key):
        del self[key]

    @classmethod
    def load_config(cls, path: Union[pathlib.Path, str]):
        with open(path, "rb") as f:
            config = tomli.load(f)
            f.close()
        return cls(config)



