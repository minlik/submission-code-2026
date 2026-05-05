from typing import Optional, Dict, Callable, Sequence, Union, Type, List
import yaml
import json
from mha.syntax import SyntaxObject, Domain, Attribute, Service, Entity
from mha.utils import pretty_yaml_dump
from .home import Home
from .device import Device
from .room import Room


__all__ = ['HomeRender']


class HomeRender(object):

    __RENDERS__: Dict[str, Dict[str, Callable]] = {}

    @staticmethod
    def builtin_device_breif_renderer(device: Device, home: Home, format: str = "json") -> str:
        room_name = home.get_room(device.room).name
        data = dict(
            did=device.did, 
            name=device.name,
            spid=device.spid,
            category=device.category,
            subcategory=device.subcategory,
            tags=device.tags,
            room=f"{room_name}(id={device.room})",
        )
        if format == "yaml":
            return yaml.dump(
                data, 
                default_flow_style=True,
                allow_unicode=True, 
                sort_keys=False,
                width=float('inf')
            ).strip()[1:-1]
        elif format == "json":
            return json.dumps(data, ensure_ascii=False)
        else:
            raise ValueError(f"Invalid format '{format}' to render")

    @staticmethod
    def builtin_device_renderer(
        device: Device, 
        home: Home, 
        attr_value: bool = True, 
        svr_code: bool = False, 
        static: bool = False,
        format: str = "json"
    ) -> str:
        def dfs(obj: SyntaxObject) -> Union[str, Dict, Sequence]:
            if isinstance(obj, Domain):
                data = {"name": obj.name}
                if obj.description is not None:
                    data['description'] = obj.description

                # userdata
                if isinstance(obj, Entity):
                    userdata = {
                        k: v for k, v in obj.userdata.items() 
                        if k in Device.STATIC_USERDATA_KEYS
                    } if static else obj.userdata
                    data.update(userdata)
                
                if len(obj.components) > 0:
                    data["components"] = [dfs(com) for com in obj.components]
                if len(obj.attributes) > 0:
                    data["attributes"] = [dfs(attr) for attr in obj.attributes]
                if len(obj.services) > 0:
                    data["services"] = [dfs(srv) for srv in obj.services]
                return data
            elif isinstance(obj, Attribute):
                data = obj.to_dict()
                if attr_value == False and 'value' in data:
                    del data['value']
                return data
            elif isinstance(obj, Service):
                data = obj.to_dict()
                if svr_code == False and 'code' in data:
                    del data['code']
                return data
            else:
                raise TypeError(f"{type(obj)} is not supported to render")

        data = dfs(device)        
        if format == 'json':
            return json.dumps(data, ensure_ascii=False)
        elif format == 'yaml':
            return pretty_yaml_dump(data)
        else:
            raise ValueError(f"Invalid format '{format}' to render")

    @staticmethod
    def builtin_device_spec_renderer(device: Device, home: Home, format: str = "json"):
        return HomeRender.render(Device, 'detail', device, home, attr_value=False, svr_code=False, static=True, format=format)
    
    @staticmethod
    def builtin_device_spec_status_renderer(device: Device, home: Home, format: str = "json") -> str:
        return HomeRender.render(Device, 'detail', device, home, attr_value=True, svr_code=False, format=format)

    @staticmethod
    def builtin_device_status_renderer(device: Device, home: Home, format: str = "json") -> str:
        def dfs(obj: SyntaxObject) -> Union[str, Dict, Sequence]:
            if isinstance(obj, Domain):
                data = {"name": obj.name}
                if obj.description is not None:
                    data['description'] = obj.description

                # userdata
                if isinstance(obj, Entity):
                    data.update(obj.userdata)
                
                if len(obj.components) > 0:
                    data["components"] = [dfs(com) for com in obj.components]
                if len(obj.attributes) > 0:
                    data["attributes"] = {attr.name: attr.value for attr in obj.attributes}
                return data
            else:
                raise TypeError(f"{type(obj)} is not supported to render")

        data = dfs(device)        
        if format == 'json':
            return json.dumps(data, ensure_ascii=False)
        elif format == 'yaml':
            return pretty_yaml_dump(data)
        else:
            raise ValueError(f"Invalid format '{format}' to render")
        
        
    @staticmethod
    def builtin_attribute_renderer(attr: Attribute, home: Home, with_value: bool = True, format: str = "json") -> str:
        data = attr.to_dict()
        if with_value == False and 'value' in data:
            del data['value']
        if format == 'json':
            return json.dumps(data, ensure_ascii=False)
        elif format == 'yaml':
            return yaml.dump(
                data, 
                default_flow_style=True, 
                allow_unicode=True, 
                sort_keys=False, 
                width=float('inf')
            ).strip()[1:-1]
        else:
            raise ValueError(f"Invalid format '{format}' to render")
        
    
    @staticmethod
    def builtin_service_renderer(service: Service, home: Home, format: str = "json") -> str:
        data = service.to_dict()
        del data['code']
        if format == 'json':
            return json.dumps(data, ensure_ascii=False)
        elif format == 'yaml':
            return yaml.dump(
                data, 
                default_flow_style=True, 
                allow_unicode=True, 
                sort_keys=False, 
                width=float('inf')
            ).strip()[1:-1]
        else:
            raise ValueError(f"Invalid format '{format}' to render")
        
    @staticmethod
    def builtin_room_renderer(room: Room, home: Home, format: str = "json") -> str:
        if format == 'json':
            return json.dumps(room.to_dict(), ensure_ascii=False)
        elif format == 'yaml':
            return yaml.dump(
                room.to_dict(), 
                default_flow_style=True, 
                allow_unicode=True, 
                sort_keys=False, 
                width=float('inf')
            ).strip()[1:-1]
        else:
            raise ValueError(f"Invalid format '{format}' to render")
    
    @staticmethod
    def register(type: Type, name: str, renderer: Callable) -> None:
        renderers = HomeRender.__RENDERS__.get(type, None)
        if renderers is None:
            renderers = HomeRender.__RENDERS__[type] = {}
        renderers[name] = renderer

    @staticmethod
    def render(type: Type, name: str, *args, **kwargs) -> str:
        renderers = HomeRender.__RENDERS__.get(type, None)
        assert renderers is not None, ValueError(f"no such renderer for type '{type}'")
        f_render = renderers.get(name, None)
        assert f_render is not None, ValueError(f"no such renderer for type '{type}' and name '{name}'")
        return f_render(*args, **kwargs)



HomeRender.register(Device, 'detail', HomeRender.builtin_device_renderer)
HomeRender.register(Device, 'brief', HomeRender.builtin_device_breif_renderer)
HomeRender.register(Device, 'spec', HomeRender.builtin_device_spec_renderer)
HomeRender.register(Device, 'status', HomeRender.builtin_device_status_renderer)
HomeRender.register(Device, 'spec_status', HomeRender.builtin_device_spec_status_renderer)

HomeRender.register(Room, 'detail', HomeRender.builtin_room_renderer)


    
