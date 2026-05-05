from typing import Optional, List, Dict
from itertools import chain
import os
import argparse
from omegaconf import OmegaConf, DictConfig
from mha.syntax import Entity, Service
from mha.utils import pretty_yaml_dump



__all__ = ['add_parser']


def add_parser(sparser: argparse._SubParsersAction):
    parser = sparser.add_parser('export', help='export completed entity configuration')
    parser.set_defaults(func=async_main)
    parser.add_argument('input', type=str, default=None, help='entity input path')
    parser.add_argument('-o', '--output', type=str, default='entity', help='entity output path')
    parser.add_argument('-i', '--include', type=str, default=None, help='include path')
    parser.add_argument('-c', '--count', type=int, default=1, help='validation count per entity')
    parser.add_argument('-m', '--merge', action='store_true', help='merge entity configuration')



def load_entities(entity_path: str, include_path: Optional[str]) -> Dict[str, List[Entity]]:

    def collect_configs(path: str) -> List[str]:
        if os.path.isdir(path):
            files = [
                os.path.join(root, file)
                for root, _, files in os.walk(path)
                for file in files
                if os.path.splitext(file)[-1] in {'.yaml', '.yml'}
            ]
        elif os.path.isfile(path):
            files = [path]
        else:
            raise FileNotFoundError(f"no such file or directory, {path}")
        return files


    # load includes
    include_confs: Dict[str, DictConfig] = {}
    if include_path is not None:
        for file in collect_configs(include_path):
            key = os.path.splitext(os.path.relpath(file, include_path))[0].replace('/', '.')
            include_confs[key] = OmegaConf.load(file)


    # register resolver
    def include_resolver(location: str):
        
        s = location.split('.')
        conf = key = None
        for i in range(len(s)):
            conf = include_confs.get('.'.join(s[:i+1]), None)
            if conf is None:
                continue
            key = '.'.join(s[i+1:])
            break
        
        if conf is None:
            raise KeyError(f"include file location '{location}' not found")

        if len(key) == 0:
            return conf
        
        conf = OmegaConf.select(conf, key)
        if conf is None:
            raise KeyError(f"include key location '{key}' not found")
        return conf
    
    OmegaConf.register_new_resolver('mha.inc', include_resolver)

    entities: Dict[str, List[Entity]] = {}
    for file in collect_configs(entity_path):
        conf = OmegaConf.load(file)
        config = OmegaConf.to_yaml(conf, resolve=True)
        key = os.path.relpath(file, entity_path)
        try:
            entities[key] = Entity.load(config)
        except Exception as e:
            raise RuntimeError(f"parse entity failed, file: '{file}', error: {e}")

    return entities


def validate(entities: List[Entity], val_count: int):
    def _call(service: Service):
        kwargs = {
            arg.name: arg.rand_value()
            for arg in service.arguments
        }
        try:
            service(**kwargs)
        except Exception as e:
            raise Exception(f"{e}, service: {service.location}")

    names, spids = set(), set()

    for entity in entities:
        # base check
        if entity.name in names:
            raise KeyError(f"repeated entity name: {entity.name}")
        spid = None if entity.userdata is None else entity.userdata.get('spid', None)
        if spid is None:
            raise KeyError(f"missing spid in userdata")
        if spid in spids:
            raise KeyError(f"repeated spid: {spid}")
        names.add(entity.name)
        spids.add(spid)

        # check
        for _ in range(val_count):
            entity = entity.rand()
            services = entity.retrieve(lambda obj: isinstance(obj, Service))
            for service in services:
                _call(service)


def output(entities: Dict[str, List[Entity]], output_path: str, merged: bool):
    if merged:
        confs = [entity.to_dict() for ents in entities.values() for entity in ents]
        with open(output_path, 'w') as f:
            pretty_yaml_dump(confs, f)
    else:
        for file, ents in entities.items():
            filepath = os.path.join(output_path, file)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            confs = ents[0].to_dict() if len(ents) == 1 else [e.to_dict() for e in ents]
            with open(filepath, 'w') as f:
                pretty_yaml_dump(confs, f)


async def async_main(args):

    # load entities
    entities = load_entities(args.input, args.include)

    # validate
    validate(list(chain(*entities.values())), args.count)

    # output
    output(entities, args.output, args.merge)

    print(f"entity export finished, path: {args.output}")