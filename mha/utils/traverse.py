from typing import Optional, Tuple, Sequence, Dict, Any
from mha.syntax import Domain, Attribute


__all__ = [
    'diff_attributes',
    'export_attribute_values',
    'apply_attribute_values',
]



def diff_attributes(lhs: Domain, rhs: Domain) -> Tuple[Sequence[Attribute], Sequence[Attribute]]:
    s1 = set([
        (attr.location, attr.value)
        for attr in lhs.retrieve(lambda node: type(node) is Attribute)
    ])
    s2 = set([
        (attr.location, attr.value)
        for attr in rhs.retrieve(lambda node: type(node) is Attribute)
    ])
    return (
        [lhs.locate(loc) for (loc, _) in s1.difference(s2)],
        [rhs.locate(loc) for (loc, _) in s2.difference(s1)],
    )


def export_attribute_values(domain: Domain) -> Dict[str, Any]:
    return {
        attr.location: attr.value
        for attr in domain.retrieve(lambda node: type(node) is Attribute)
    }


def apply_attribute_values(domain: Domain, values: Dict[str, Any]) -> None:
    for attr in domain.retrieve(lambda node: type(node) is Attribute):
        if attr.location in values:
            attr.value = values[attr.location]


