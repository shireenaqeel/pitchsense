"""Upload the assembled Space and wait until it is running.

Run by .github/workflows/huggingface.yml from the repo root, with the Space
contents in ./space. Exits non-zero if the Space fails to build or start, so the
workflow run fails and GitHub sends its failure email.
"""

import os
import sys
import time

from huggingface_hub import HfApi

SPACE = os.environ["SPACE"]
FAILED = {"BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR", "NO_APP_FILE", "DELETING"}
TIMEOUT = 20 * 60

api = HfApi(token=os.environ["HF_TOKEN"])

# The leaderboard's Supabase settings live in GitHub's secrets and are copied to
# the Space's, so they are managed in one place.
for name in ("SUPABASE_URL", "SUPABASE_KEY"):
    if os.environ.get(name):
        api.add_space_secret(SPACE, name, os.environ[name])
    else:
        print(f"::warning::{name} is not set, so the Space's leaderboard resets on restart")

commit = api.upload_folder(
    repo_id=SPACE, repo_type="space", folder_path="space",
    commit_message=f"Deploy {os.environ['SHA'][:7]}", delete_patterns=["*"],
)
print(f"Uploaded {commit.oid[:7]}; waiting for the Space to build")

# A fresh upload takes a moment to register as a new build.
time.sleep(30)
deadline = time.monotonic() + TIMEOUT
while time.monotonic() < deadline:
    stage = api.get_space_runtime(SPACE).stage
    print(f"Space stage: {stage}")
    if stage == "RUNNING":
        sys.exit(0)
    if stage in FAILED:
        print(f"::error::The Space stopped at {stage}; see its Logs tab on Hugging Face")
        sys.exit(1)
    time.sleep(20)
print("::error::The Space did not start within 20 minutes")
sys.exit(1)
