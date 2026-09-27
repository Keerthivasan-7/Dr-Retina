import asyncio
import selectors
import sys


def loop_factory():
    # Psycopg async I/O needs add_reader/add_writer; Windows Proactor lacks them.
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())
    return asyncio.new_event_loop()
