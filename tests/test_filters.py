from typing import Optional

from ffmpeg_chain.core.filters import FilterNode


class TestFilterNode:
    def test_filter_node_creation(self) -> None:
        node = FilterNode("scale")
        assert node.filter_name == "scale"
        assert not node.filter_args
        assert node.next_node is None

    def test_filter_node_with_args(self) -> None:
        node = FilterNode("scale", width="1280", height="-1")
        assert node.filter_name == "scale"
        assert node.filter_args == {"width": "1280", "height": "-1"}

    def test_filter_node_str_no_args(self) -> None:
        node = FilterNode("scale")
        assert str(node) == "scale"

    def test_filter_node_str_with_args(self) -> None:
        node = FilterNode("scale", width="1280", height="-1")
        assert str(node) == "scale=width=1280:height=-1"

    def test_filter_node_chaining(self) -> None:
        node1: FilterNode = FilterNode("scale", width="1280")
        node2: FilterNode = FilterNode("fps", fps="30")
        node1.next_node = node2

        current: Optional[FilterNode] = node1
        nodes: list[str] = []
        while current is not None:
            nodes.append(str(current))
            current = current.next_node

        assert nodes == ["scale=width=1280", "fps=fps=30"]

    def test_filter_node_empty_args_dict(self) -> None:
        node = FilterNode("scale")
        assert str(node) == "scale"

    def test_filter_node_multiple_args_order(self) -> None:
        # Test that args are consistently ordered in the string representation
        kwargs = {"b": "2", "a": "1", "c": "3"}
        node = FilterNode("test", **kwargs)
        result = str(node)
        # Split the result and check parts
        parts = result.replace("test=", "").split(":")
        assert len(parts) == len(kwargs)
        # Verify all arg pairs are present
        assert all(f"{k}={v}" in parts for k, v in kwargs.items())
