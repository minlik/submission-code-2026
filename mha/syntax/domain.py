from typing import Optional, Sequence, Any, Dict, Tuple, Union, Callable
from collections.abc import ItemsView, ValuesView, KeysView
import yaml
import io
import copy
from .object import SyntaxObject, register
from .attribute import Attribute, Argument
from .service import Service


__all__ = ['Domain', 'Component', 'Entity']



class Domain(SyntaxObject):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__dict__['__init_end__'] = True

    @property
    def attributes(self) -> Sequence[Attribute]:
        return self._type_children.get(Attribute, [])
    
    @property
    def services(self) -> Sequence[Service]:
        return self._type_children.get(Service, [])
    
    @property
    def components(self) -> Sequence["Component"]:
        return self._type_children.get(Component, [])
    
    def __str__(self):
        content = ", ".join([str(v) for v in [
            self.name,
            None if len(self.attributes) == 0 else f"attrs=[{','.join([a.name for a in self.attributes])}]",
            None if len(self.services) == 0 else f"sevrs=[{','.join([s.name for s in self.services])}]",
        ] if v is not None])
        return f"{self.__class__.__name__}({content})"
    
    __repr__ = __str__
    
    def __contains__(self, key: str) -> bool:
        return key in self._children_dict
    
    def __getitem__(self, key: str) -> SyntaxObject:
        return self.locate(key)
    
    def __setattr__(self, key: str, value: Any):
        if '__init_end__' not in self.__dict__:
            self.__dict__[key] = value
            return
        
        obj = self._children_dict.get(key, None)
        assert obj is not None, f"{self.name} has no attribute {key}"
        assert isinstance(obj, Attribute), f"{self.name}.{key} is not an attribute, but {type(obj)}"
        obj.value = value

    __getattr__ = __getitem__

    def __call__(self, name: str, *args, **kwds):
        service = self.locate(name)
        if not isinstance(service, Service):
            raise TypeError(f"{name} is not service, but {type(service)}")
        return service(*args, **kwds)
    
    def keys(self) -> KeysView[str]:
        return self._children_dict.keys()

    def values(self) -> ValuesView[SyntaxObject]:
        return self._children_dict.values()
    
    def items(self) -> ItemsView[str, SyntaxObject]:
        return self._children_dict.items()
    
    def rand(self, callback: Optional[Callable[[Callable], Any]] = None):
        dft_callback = lambda obj: obj.rand_value()
        f_callback = dft_callback if callback is None else callback
        def _rand_attr(obj: SyntaxObject):
            if not isinstance(obj, Attribute) or isinstance(obj, Argument):
                return
            obj.value = f_callback(obj)
        entity: Entity = self.copy()
        entity.traverse(_rand_attr)
        return entity


class Component(Domain):
    pass


class Entity(Component):
    def __init__(self, userdata: Optional[Dict] = None, **kwargs):
        self._userdata = {} if userdata is None else copy.deepcopy(userdata)
        super().__init__(**kwargs)
        
    @property
    def userdata(self) -> Dict:
        return self._userdata
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if len(self._userdata) > 0:
            d.update(userdata=copy.deepcopy(self._userdata))
        return d
    
    @staticmethod
    def load(stream: Union[Dict, str, io.TextIOBase]) -> Sequence["Entity"]:
        if isinstance(stream, (str, io.TextIOBase)):
            datas = yaml.load(stream, Loader=yaml.FullLoader)
        else:
            datas = stream
        if isinstance(datas, dict):
            return [Entity.from_dict(datas)]
        elif isinstance(datas, (tuple, list)):
            return [Entity.from_dict(data) for data in datas]
        else:
            raise TypeError(f"invalid entity data type {type(datas)}, expected: dict, tuple, list")


register(Component)