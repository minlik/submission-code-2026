from typing import Dict, Sequence, Union
import json
import yaml
import os


__all__ = [
    'Config'
]


class Config(object):

    LoadReturnType = Union[Dict, Sequence]

    _ROOT_PATH: str = os.path.dirname(os.path.abspath(__file__))

    _CONFIGS: Dict = {}

    @staticmethod
    def get_root_path() -> str: return Config._ROOT_PATH

    @staticmethod
    def load_config(filename: str):
        config = Config._CONFIGS.get(filename, None)
        if config is None:
            config = Config.load(os.path.join(Config.get_root_path(), filename))
            Config._CONFIGS[filename] = config
        return config

    @staticmethod
    def load_device() -> Sequence[Dict]:
        return Config.load_config('device.yaml')
    
    @staticmethod
    def load_behavior() -> Sequence[Dict]:
        return Config.load_config('behavior.yaml')

    @staticmethod
    def load(filepath: str, **kwargs) -> LoadReturnType:
        def _jsonl(f):
            skip_empty = kwargs.get('skip_empty_line', False)
            datas = []
            for ln in f.readlines():
                if skip_empty and len(ln) == 0:
                    continue
                datas.append(json.loads(ln))
            return datas

        ext_loaders = {
            '.json': lambda f: json.load(f),
            '.yaml': lambda f: yaml.load(f, Loader=yaml.FullLoader),
            '.jsonl': _jsonl
        }

        # check loader
        ext = os.path.splitext(filepath)[-1]
        loader = ext_loaders.get(ext, None)
        if loader is None:
            raise NotImplementedError(f"extension '{ext}' is not support for loading, file: {filepath}")

        # check file existed
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"no such file '{filepath}'")

        # open and load
        with open(filepath, 'r') as f:
            return loader(f)
