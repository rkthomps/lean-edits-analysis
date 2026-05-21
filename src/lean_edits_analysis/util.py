from edit_data.types import Range as EditRange

from lean_client.client import Range, Position


def to_client_range(range: EditRange) -> Range:
    return Range(
        start=Position(line=range.start.line, character=range.start.character),
        end=Position(line=range.end.line, character=range.end.character),
    )
