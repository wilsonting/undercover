"""Run the UnderCover Agent from the terminal.

uv run -m agent CLM-1001 decides one claim; uv run -m agent works the whole queue.
"""

import sys
from uuid import uuid4

from agent.main import run, work_the_queue

match sys.argv[1:]:
    case [claim_id]:
        print(run(claim_id, str(uuid4())))
    case []:
        work_the_queue()
    case _:
        sys.exit(
            "Usage: uv run -m agent [claim id]. Give one claim id, such as CLM-1001,"
            " or none to work every waiting claim."
        )
