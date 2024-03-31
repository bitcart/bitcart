from typing import TypeVar

Money = TypeVar("Money", bound=str)


class StrEnumMeta(type):
    def __new__(cls, name, bases, attrs):
        new_class = type.__new__(cls, name, bases, attrs)
        new_class.__enum_fields__ = list(
            map(lambda x: x.lower(), [getattr(new_class, attr) for attr in dir(new_class) if attr.upper() == attr])
        )
        return new_class

    def __contains__(cls, v):
        return v in cls.__enum_fields__

    def __iter__(cls):
        return iter(cls.__enum_fields__)


class StrEnum(metaclass=StrEnumMeta):
    pass
