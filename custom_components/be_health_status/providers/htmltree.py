"""A very small DOM built on the standard library, so no extra requirements are needed."""

from __future__ import annotations

from collections.abc import Iterator
from html.parser import HTMLParser

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Node:
    """An element with its attributes, children and text."""

    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: dict[str, str], parent: Node | None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[Node | str] = []
        self.parent = parent

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def text(self, sep: str = "") -> str:
        """All text inside this element, with <br> as a space, whitespace collapsed."""
        parts: list[str] = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag == "br":
                parts.append(" ")
            else:
                parts.append(child.text(sep))
            parts.append(sep)
        return " ".join("".join(parts).split())

    def iter(self) -> Iterator[Node]:
        """This element and every element below it, in document order."""
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.iter()

    def find_all(self, tag: str | None = None, cls: str | None = None) -> list[Node]:
        return [
            n
            for n in self.iter()
            if (tag is None or n.tag == tag) and (cls is None or cls in n.classes)
        ]

    def find(self, tag: str | None = None, cls: str | None = None) -> Node | None:
        return next(iter(self.find_all(tag, cls)), None)


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, None)
        self._cur = self.root

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: v or "" for k, v in attrs}, self._cur)
        self._cur.children.append(node)
        if tag not in _VOID:
            self._cur = node

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._cur.children.append(Node(tag, {k: v or "" for k, v in attrs}, self._cur))

    def handle_endtag(self, tag: str) -> None:
        node = self._cur
        while node is not self.root and node.tag != tag:
            node = node.parent  # type: ignore[assignment]
        if node is not self.root:
            self._cur = node.parent  # type: ignore[assignment]

    def handle_data(self, data: str) -> None:
        self._cur.children.append(data)


def parse_html(html: str) -> Node:
    """Parse an HTML document into a Node tree."""
    builder = _Builder()
    builder.feed(html)
    builder.close()
    return builder.root
