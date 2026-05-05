import yaml


__all__ = ['Dumper', 'pretty_yaml_dump']


class Dumper(yaml.SafeDumper):
    def represent_list(self, data):
        types = {type(d) for d in data}
        if all([t in {int, float, str} for t in types]):
            return self.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

        return self.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=False)

    def represent_str(self, data):
        if '\n' in data:
            return self.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return self.represent_scalar('tag:yaml.org,2002:str', data, style='')



Dumper.add_representer(str, Dumper.represent_str)
Dumper.add_representer(list, Dumper.represent_list)
Dumper.add_representer(tuple, Dumper.represent_list)


def pretty_yaml_dump(data, stream=None, **kwds):
    if 'allow_unicode' not in kwds:
        kwds['allow_unicode'] = True
    if 'sort_keys' not in kwds:
        kwds['sort_keys'] = False
    return yaml.dump(data, stream=stream, Dumper=Dumper, **kwds)