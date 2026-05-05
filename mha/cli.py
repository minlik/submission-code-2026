import sys
import asyncio
import argparse
from mha import cmd


def parse_args():
    parser = argparse.ArgumentParser(prog='home assistant', description="home assistant syntax and proto parser",)
    sparser = parser.add_subparsers()

    for c in cmd.all():
        c.add_parser(sparser)

    # parse
    args = parser.parse_args()

    # check
    if getattr(args, 'func', None) is None:
        parser.print_help()
        sys.exit(0)

    return args

async def async_main():
    args = parse_args()
    await args.func(args)

def main():
    asyncio.run(async_main())