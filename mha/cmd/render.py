from typing import Optional, List, Dict
import argparse
import random
from mha.syntax import Attribute, Service
from mha.engine import HomeEngine, HomeSampler, HomeRender, Device, Room




__all__ = ['add_parser']


def add_parser(sparser: argparse._SubParsersAction):
    parser = sparser.add_parser('render', help='render a syntax object')
    parser.set_defaults(func=async_main)
    parser.add_argument('-t', '--type', type=str, choices=["device", "room"], help='syntax object type')
    parser.add_argument('-m', '--mode', type=str, help='render mode')
    parser.add_argument('-f', '--format', type=str, default="json", help='render mode')
    

async def async_main(args):
    engine = HomeEngine(home=HomeSampler.sample_test())

    if args.type == "device":
        tp = Device
        obj = random.choice(engine.home.devices)
    elif args.type == "room":
        tp = Room
        obj = random.choice(engine.home.rooms)
    else:
        raise ValueError(f"invalid type '{args.type}' for render")

    print(HomeRender.render(tp, args.mode, obj, engine.home, args.format))


    