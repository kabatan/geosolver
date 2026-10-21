"""Collect completed external-teacher batches without changing their answers."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    requests = json.loads((HERE / "teacher_requests.json").read_text())
    candidates = []
    for i, request in enumerate(requests, 1):
        path = HERE / f"raw-batch{i}.txt"
        if not path.exists():
            continue
        batch = json.loads(path.read_text())
        assert [row["id"] for row in batch] == request["ids"], path
        for row in batch:
            assert row["status"] in ("complete", "unresolved"), row
            assert "answer" in row and "method" in row and "audit_note" in row, row
            candidates.append({**row, "source": request["chat_url"]})
    assert len(candidates) == len({row["id"] for row in candidates})
    (HERE / "candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"Collected {len(candidates)} candidates; complete "
          f"{sum(row['status'] == 'complete' for row in candidates)}.")


if __name__ == "__main__":
    main()
