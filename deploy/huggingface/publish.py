"""Upload the built game to its static Hugging Face Space and wait until it serves.

Run by the huggingface job in .github/workflows/game.yml, with the built game
and the Space's README in ./space. Exits non-zero if the Space doesn't come up,
so the run fails and GitHub sends its failure email.
"""

import os
import sys
import time

from huggingface_hub import HfApi

SPACE = os.environ["SPACE"]
FAILED = {"BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR", "NO_APP_FILE", "DELETING"}
TIMEOUT = 10 * 60

api = HfApi(token=os.environ["HF_TOKEN"])
commit = api.upload_folder(
    repo_id=SPACE, repo_type="space", folder_path="space",
    commit_message=f"Deploy {os.environ['GITHUB_SHA'][:7]}", delete_patterns=["*"],
)
print(f"Uploaded {commit.oid[:7]}; waiting for the Space")

time.sleep(15)
deadline = time.monotonic() + TIMEOUT
while time.monotonic() < deadline:
    stage = api.get_space_runtime(SPACE).stage
    print(f"Space stage: {stage}")
    if stage == "RUNNING":
        sys.exit(0)
    if stage in FAILED:
        print(f"::error::The Space stopped at {stage}; see its page on Hugging Face")
        sys.exit(1)
    time.sleep(15)
print("::error::The Space did not come up within 10 minutes")
sys.exit(1)
