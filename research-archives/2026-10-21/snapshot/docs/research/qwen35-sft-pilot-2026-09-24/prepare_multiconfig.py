"""Select verbatim complete subanswers after independent mathematical audit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = Path("qwen/.runtime/qwen35_sft_pilot_20260924/thinking-material-20260924")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    selected = []
    provenance = []
    for id, source, end_marker in (
        ("DA04-broaden-thinking-0", "DA04", "$$TQ = 25$$"),
        ("DA15-fresh-thinking-0", "DA15", "$\\angle BFO = \\angle BCO$ と置換できる。"),
    ):
        path = SOURCES / (id + ".json")
        record = json.loads(path.read_text())
        final = record["final_text"]
        start = final.index("(1) 関係と条件")
        end = final.index(end_marker, start) + len(end_marker)
        answer = final[start:end]
        assert answer in final and "<think>" not in answer and "<|im_" not in answer
        prompt = record["messages"][0]["content"]
        selected.append(dict(id=id + "-verified-subanswer", source=source,
                             prompt=prompt, answer=answer, origin_file=str(path),
                             origin_sha256=sha(path), selection_provenance=str(HERE / "candidate-thinking-provenance.json")))
        provenance.append(dict(id=id, source=source, origin_file=str(path),
                               origin_sha256=sha(path), final_char_start=start, final_char_end=end,
                               selected_sha256=hashlib.sha256(answer.encode()).hexdigest(),
                               verifier="verify_thinking.py and manual proof review"))
    existing = json.loads((HERE / "train-h01-technical.json").read_text())[0]
    dataset = [existing] + selected
    (HERE / "candidate-thinking-provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    for row in selected:
        (HERE / ("candidate-" + row["source"].lower() + "-thinking.txt")).write_text(row["answer"] + "\n")
    output = HERE / "train-multiconfig.json"
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n")
    hparams = json.loads((HERE / "sft-hparams.json").read_text())
    hparams.update(dataset=str(output), dataset_sha256=sha(output),
                   eval_jobs_sha256=sha(HERE / "proof-eval-jobs.json"),
                   model_revision="c202236235762e1c871ad0ccb60c8ee5ba337b9a",
                   n_examples=len(dataset), n_configurations=3,
                   study_arm="three_configuration_self_generated_sft")
    protocol = HERE / "sft-multiconfig-protocol.json"
    protocol.write_text(json.dumps(hparams, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(dataset=str(output), sha256=sha(output),
                          protocol=str(protocol), configurations=[x["source"] for x in dataset])))


if __name__ == "__main__":
    main()
