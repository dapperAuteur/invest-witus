import sys

import invest_witus


def test_python_is_3_14_or_newer() -> None:
    assert sys.version_info >= (3, 14)


def test_the_package_imports() -> None:
    assert invest_witus.__name__ == "invest_witus"
