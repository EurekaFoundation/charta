from charta.items.base import FrameItem
from charta.items.group import GroupFrame
from charta.items.image import ImageFrame
from charta.items.shape import ShapeFrame
from charta.items.text import TextFrame


def item_from_dict(d: dict, document) -> FrameItem | None:
    kind = d.get("type")
    if kind == "text":
        item = TextFrame()
    elif kind == "image":
        item = ImageFrame(document)
    elif kind == "shape":
        item = ShapeFrame(d.get("shape", "rect"))
    elif kind == "group":
        item = GroupFrame()
        item.apply_dict(d, document)
        return item
    else:
        return None  # tipo sconosciuto (file di una versione futura): lo ignoriamo
    item.apply_dict(d)
    return item


__all__ = ["FrameItem", "TextFrame", "ImageFrame", "ShapeFrame", "GroupFrame", "item_from_dict"]
