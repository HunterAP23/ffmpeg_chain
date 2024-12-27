from typing import Optional


class FilterNode:
    """Represents a single filter in a filterchain."""

    def __init__(self, filter_name: str, **kwargs: str) -> None:
        self.filter_name: str = filter_name
        self.filter_args: dict[str, str] = kwargs
        self.next_node: Optional[FilterNode] = None

    def __str__(self) -> str:
        if not self.filter_args:
            return self.filter_name
        args_str = ":".join(f"{k}={v}" for k, v in self.filter_args.items())
        return f"{self.filter_name}={args_str}"
