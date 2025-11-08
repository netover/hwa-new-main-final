from collections.abc import AsyncIterator


async def create_text_stream(chunks: list[str]) -> AsyncIterator[str]:
    """
    Creates an asynchronous iterator from a list of strings,
    simulating a text stream.
    """
    for chunk in chunks:
        yield chunk
