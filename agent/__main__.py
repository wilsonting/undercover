"""Run the UnderCover Agent on one claim: uv run -m agent CLM-1001"""

import sys
from uuid import uuid4

from agent.main import run

match sys.argv[1:]:
    case [claim_id]:
        print(run(claim_id, str(uuid4())))
    case _:
        sys.exit(
            "Usage: uv run -m agent <claim id>, for example uv run -m agent CLM-1001"
        )
