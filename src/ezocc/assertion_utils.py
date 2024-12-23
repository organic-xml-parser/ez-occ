

def assert_greater_than_0(name: str, variable: float):
    if variable <= 0:
        raise ValueError(f"{name} must be > 0")


def assert_greater_than(more_name: str, more_value: float, less_name: str, less_value: float):
    if less_value >= more_value:
        raise ValueError(f"{more_name} must be > {less_name}")