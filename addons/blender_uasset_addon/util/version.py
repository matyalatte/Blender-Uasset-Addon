"""Class for version info.

Notes:
    Variables:
        base: Base version like 1.2, 2.3.0.
        base_int: Base version as int. 1 will be 10000. 4.27 will be 42700. 5.0.2 will be 50002.
        custom: custom string for customized version.
    Operators:
        ==, !=: Comparison operators for base and custom.
                If the input is a list, it will be "in" operator
        <, <=, >, >=: Comparison operators for base_int.
"""


class VersionInfo:
    """Class for version info."""

    def __init__(self, base_version, customized_version=None, base_int=None):
        """Constractor."""
        self.base = base_version
        self.custom = customized_version
        if base_int is None:
            self.base_int = version_as_int(self.base)
        else:
            self.base_int = base_int

    def copy(self):
        """Copy itself."""
        return VersionInfo(self.base, customized_version=self.custom, base_int=self.base_int)

    def __eq__(self, item):  # self == item
        """Equal operator."""
        if isinstance(item, str):
            return item in [self.base, self.custom]
        if isinstance(item, list):
            return self.base in item or self.custom in item
        raise RuntimeError(f"Comparison method doesn't support {type(item)}.")

    def __ne__(self, item):  # self != item
        """Neq operator."""
        if isinstance(item, str):
            return self.base != item and self.custom != item
        if isinstance(item, list):
            return (self.base not in item) and (self.custom not in item)
        raise RuntimeError(f"Comparison method doesn't support {type(item)}.")

    def __lt__(self, v):  # self < string
        """Less than."""
        return self.base_int < version_as_int(v)

    def __le__(self, v):  # self <= string
        """Less than or equal to."""
        return self.base_int <= version_as_int(v)

    def __gt__(self, v):  # self > string
        """Greater than."""
        return self.base_int > version_as_int(v)

    def __ge__(self, v):  # self >= string
        """Greater than or equal to."""
        return self.base_int >= version_as_int(v)

    def __str__(self):  # str(self)
        """To string."""
        if self.custom is not None:
            return self.custom
        return self.base


def version_as_int(ver):  # ver (string): like "x.x.x"
    """Convert a string to int."""
    ver_str = [int(s) for s in ver.split('.')]
    if len(ver_str) > 3:
        raise RuntimeError(f'Unsupported version info.({ver})')
    return sum(s * (10 ** ((2 - i) * 2)) for s, i in zip(ver_str, range(len(ver_str))))
