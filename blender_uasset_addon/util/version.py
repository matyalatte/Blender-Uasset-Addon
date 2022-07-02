# Class for version info.
#  Variables:
#    base: Base version like 1.2, 2.3.0.
#    base_int: Base version as int. 1 will be 10000. 4.27 will be 42700. 5.0.2 will be 50002.
#    custom: custom string for customized version.
#  Operators:
#    ==, !=: Comparison operators for base and custom.
#            If the input is a list, it will be "in" operator
#    <, <=, >, >=: Comparison operators for base_int.

class VersionInfo:
    def __init__(self, base_version, customized_version=None, base_int=None):
        self.base = base_version
        self.custom = customized_version
        if base_int is None:
            self.base_int = version_as_int(self.base)
        else:
            self.base_int = base_int

    def copy(self):
        return VersionInfo(self.base, customized_version=self.custom, base_int=self.base_int)

    def __eq__(self, item):  # self == item
        if isinstance(item, str):
            return self.base == item or self.custom == item
        elif isinstance(item, list):
            return self.base in item or self.custom in item
        else:
            raise RuntimeError("Comparison method doesn't support {}.".format(type(item)))

    def __nq__(self, item):  # self != item
        if isinstance(item, str):
            return self.base != item and self.custom != self.custom
        elif isinstance(item, list):
            return (self.base not in item) and (self.custom not in item)
        else:
            raise RuntimeError("Comparison method doesn't support {}.".format(type(item)))

    def __lt__(self, v):  # self < string
        return self.base_int < version_as_int(v)

    def __le__(self, v):  # self <= string
        return self.base_int <= version_as_int(v)

    def __gt__(self, v):  # self > string
        return self.base_int > version_as_int(v)

    def __ge__(self, v):  # self >= string
        return self.base_int >= version_as_int(v)

    def __str__(self):  # str(self)
        if self.custom is not None:
            return self.custom
        else:
            return self.base


def version_as_int(ver):  # ver: string like "x.x.x"
    ver_str = [int(s) for s in ver.split('.')]
    if len(ver_str) > 3:
        raise RuntimeError('Unsupported version info.({})'.format(ver))
    return sum([s * (10 ** ((2 - i) * 2)) for s, i in zip(ver_str, range(len(ver_str)))])
