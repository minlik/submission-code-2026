from typing import Optional, List, Type, Dict, Any, Callable, Union
from .event import IEvent


__all__ = ['SyntaxObject', 'register']


class SyntaxObject(IEvent):
    def __init__(self, name: str, description: Optional[str] = None, **kwargs):
        if not isinstance(name, str):
            raise ValueError(f"invalid name type '{type(name)}' for {self.__class__.__name__}, expected: str")

        self._name: str = name
        self._description: Optional[str] = description
        self._parent: Optional["SyntaxObject"] = None
        self._children: List["SyntaxObject"] = []
        self._children_dict: Dict[str, "SyntaxObject"] = {}
        self._type_children: Dict[Type[SyntaxObject], List[SyntaxObject]] = {}

        # parse childs
        for key, children in kwargs.items():
            ctype = __REGISTER_TABLE__.get(key[:-1], None)  # remove last char 's'
            if ctype is None:
                raise KeyError(f"no such syntax type '{ctype}'")
            for child in children:
                self.add_child(child, ctype)

    @property
    def name(self) -> str:
        return self._name

    @property    
    def description(self) -> Optional[str]:
        return self._description

    @property
    def parent(self) -> Optional["SyntaxObject"]:
        return self._parent
    
    @property
    def root(self) -> "SyntaxObject":
        return self if self._parent is None else self._parent.root
    
    @property
    def location(self) -> str:
        if self.parent is None:
            return ''
        ploc = self.parent.location
        return self.name if len(ploc) == 0 else f"{self.parent.location}.{self.name}"
    
    def locate(self, location: str) -> "SyntaxObject":
        names = location.split('.')
        def _dfs(node: "SyntaxObject", index: int):
            if index >= len(names):
                return node
            child = node._children_dict.get(names[index], None)
            if child is None:
                cur_name = node.name if len(node.location) == 0 else node.location
                raise AttributeError(f"'{cur_name}' has no Attribute or Service '{names[index]}'") # must be AttributeError for getattr
            return _dfs(child, index + 1)
        
        return _dfs(self, 0)

    def traverse(self, callback: Callable[["SyntaxObject"], None]) -> None:
        def _dfs(node: "SyntaxObject"):
            callback(node)
            for child in node._children:
                _dfs(child)
        return _dfs(self)
    
    def retrieve(self, callback: Callable[["SyntaxObject"], bool]) -> List["SyntaxObject"]:
        nodes = []
        def _check(node: "SyntaxObject"):
            nonlocal nodes
            if callback(node):
                nodes.append(node)
        self.traverse(_check)
        return nodes
    
    def add_child(self, child: Union[Dict, "SyntaxObject"], ctype: Optional[Union[str, Type["SyntaxObject"]]] = None) -> "SyntaxObject":
        # type
        otype: Optional[Type[SyntaxObject]] = None
        if ctype is not None:
            if isinstance(ctype, str):
                otype = __REGISTER_TABLE__.get(ctype, None)
                assert otype is not None, f"invalid syntax type '{ctype}'"
            else:
                assert ctype.__name__ in __REGISTER_TABLE__, f"invalid syntax type '{ctype}'"
                otype = ctype

        # child
        if isinstance(child, SyntaxObject):
            if otype is not None:
                assert type(child) == otype, f"mismatch child type, child: {type(child)}, type: {otype}"
            else:
                assert type(child).__name__ in __REGISTER_TABLE__, f"invalid child type '{type(child).__name__}'"
            obj = child
        elif isinstance(child, dict):
            assert otype is not None, f"missing type for dict child"
            obj = otype.from_dict(child)
        else:
            raise TypeError(f"invalid child type '{type(child)}'  expected: SyntaxObject or dict, child: {child}")

        # check
        if obj.name in self._children_dict:
            raise RuntimeError(f"child already exists: {obj.name}")
        
        if obj.parent is not None:
            raise RuntimeError(f"child '{obj.name}' already has a parent: {obj.parent.name}") 
        
        # children
        self._children.append(obj)
        self._children_dict[obj.name] = obj

        # type to children
        tp_list = self._type_children.get(type(obj), None)
        if tp_list is None:
            tp_list = self._type_children[type(obj)] = []
        tp_list.append(obj)

        # set parent
        obj.__dict__['_parent'] = self

        # notify
        self.on_child_add(obj)

        return obj
        
    @classmethod
    def from_dict(cls: Type["SyntaxObject"], d: Dict[str, Any]) -> "SyntaxObject":
        return cls(**d)
    
    def to_dict(self) -> Dict[str, Any]:
        # name
        d = {'name': self._name}
        
        # description
        if self._description is not None:
            d['description'] = self._description

        # children
        for child in self._children:
            key = f"{type(child).__name__.lower()}s"
            children = d.get(key, None)
            if children is None:
                children = d[key] = []
            children.append(child.to_dict())
        return d

    def copy(self) -> "SyntaxObject":
        d = self.to_dict()
        return self.__class__.from_dict(d)

    def on_child_add(self, child: "SyntaxObject") -> None:
        pass



__REGISTER_TABLE__: Dict[str, Type[SyntaxObject]] = {}

def register(type: Type[SyntaxObject]):
    global __REGISTER_TABLE__
    if type in __REGISTER_TABLE__:
        raise KeyError(f"syntax type '{type}' already registered")
    if SyntaxObject not in type.__mro__:
        raise TypeError(f"invalid syntax type '{type}', expected: child of SyntaxObject")
    __REGISTER_TABLE__[type.__name__] = type
    __REGISTER_TABLE__[type.__name__.lower()] = type