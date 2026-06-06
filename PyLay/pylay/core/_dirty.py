_flag: bool = False


def mark() -> None:
    global _flag
    _flag = True


def consume() -> bool:
    global _flag
    v = _flag
    _flag = False
    return v
