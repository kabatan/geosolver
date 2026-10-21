"""Operational A/B runner. No GPU import, write, or branch selection by default.

Usage (repository root):
  .venv/bin/python docs/research/night-recipe-search-2026-09-29/branch_runner.py
  .venv/bin/python .../branch_runner.py --evidence /absolute/branch-ready.json
  .venv/bin/python -u .../branch_runner.py --evidence /absolute/branch-ready.json --execute

--execute requires a parent-created metadata receipt, schema_version=1,
status="ready", with artifacts mapping each role below to {path, sha256}:
  decision, initial_scores, initial_all_stages, review_packets, review_mapping, review_grades,
  review_receipt, review_completion, decision_execution, mechanical_audit,
  frozen_manifest, completion_policy, timing_policy, gpu_priority_policy.
initial_scores and initial_all_stages must be immutable phase copies. All paths
must be in this runtime. Other roles may also be immutable copies. No review
packets, mappings or grades are parsed by this runner; their bytes are hashed.

review_completion JSON must assert status="complete", canonical=true,
full_text_coverage=true, all_packets_graded=true, packet_count==graded_count,
and bind packet_sha256, mapping_sha256, grades_sha256, review_receipt_sha256.
decision_execution JSON must assert status="complete", returncode=0,
after_canonical_grade_save=true, and bind decision_sha256, grades_sha256,
mapping_sha256, scores_sha256, all_stages_sha256, decide_sha256. The parent creates these receipts
only after the actual full-text review and unchanged decide.py have completed.

The frozen initial comparison is independently replay-checked from generation
metadata, including all cap groups and expected final files. The ready receipt
does not waive missing, censored gate evidence or any hash/receipt mismatch.
Plan-only with evidence performs these CPU checks but does not write anything.
Runtime writes are confined to branch/, extensions/jobs-{confirmation,precision}
and branch outputs/checkpoints through the unchanged guarded campaign functions.
This program does not grade, run decide.py, mark the campaign complete, or retry
failed jobs automatically. Preserve failed attempts before authorized recovery.

Parent helper (only after audited receipts exist):
  record = evidence_record({role: absolute_path for role in ARTIFACT_ROLES})
  save_once(RUN / 'branch-ready.json', record)
This helper binds files by hash; it never fabricates the review/decision claims.
"""
import argparse
import contextlib
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_RUN = ROOT / 'qwen/.runtime/night_recipe_search_20260929'
BOUNDS = ((32768, 40960), (81920, 98304), (131072, 147456))
INITIAL_ARMS = ('Base', 'S128', 'X128', 'S512', 'X512', 'D512', 'DX512')
ORIGINAL_B = ('Base', 'D512', 'DX512')
A_CHOICES = {'S128': ('S', 'X', 128, 'X128'),
             'S512': ('S', 'X', 512, 'X512'),
             'D512': ('D', 'DX', 512, 'DX512')}
REVISION = 'c202236235762e1c871ad0ccb60c8ee5ba337b9a'
# These scripts were completed after the original 76-file manifest was sealed.
# Independently committed from the CPU branch-execution-plan.json; never pretend
# they were members of that original manifest.
SCIENTIFIC_SOURCE_SHA256 = {
    'score.py': '704390d50f7fb77aeb4a9a34457c49a67b56f5a8aff987067ec896f4f53bc57a',
    'decide.py': '0790713bcadd8cfe5868d6ba15f078f3e9468f33d57dd6cd2737f428d477e5f9',
    'audit.py': 'fe3b117702fa5fe49634989ad66e329e563180fcd6baf896b14a5464691f75c4',
}
PARAMETERS = ('seed', 'learning_rate', 'grad_accumulation', 'grad_clip',
              'lora_rank', 'lora_alpha', 'lora_modules', 'ce_chunk_tokens',
              'max_target_tokens', 'max_sequence_tokens', 'enable_thinking')
ARTIFACT_ROLES = ('decision', 'initial_scores', 'initial_all_stages', 'review_packets', 'review_mapping',
                  'review_grades', 'review_receipt', 'review_completion',
                  'decision_execution', 'mechanical_audit', 'frozen_manifest',
                  'completion_policy', 'timing_policy', 'gpu_priority_policy')


class EvidenceError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def read(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise EvidenceError(f'Missing or invalid JSON: {path}') from exc


def sha(path):
    h = hashlib.sha256()
    try:
        with Path(path).open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(chunk)
    except OSError as exc:
        raise EvidenceError(f'Missing file to hash: {path}') from exc
    return h.hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save_once(path, value):
    """Atomic creation; an existing record must be exactly the same value."""
    path = Path(path)
    if path.exists():
        require(read(path) == value, f'Existing operational record differs: {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # link is atomic and cannot overwrite a concurrent author's record.
        try:
            os.link(temporary, path)
        except FileExistsError:
            require(read(path) == value, f'Concurrent operational record differs: {path}')
    finally:
        temporary.unlink(missing_ok=True)


def evidence_record(artifact_paths):
    """Hash already prepared evidence. Full validation remains mandatory at launch."""
    require(set(artifact_paths) == set(ARTIFACT_ROLES), 'Missing/unknown evidence artifact roles')
    return dict(schema_version=1, status='ready', artifacts={role: dict(path=str(Path(path).resolve()), sha256=sha(path))
                for role, path in artifact_paths.items()})


def batches(jobs):
    require(jobs and len({j['id'] for j in jobs}) == len(jobs), 'Empty/duplicate jobs')
    result = {}
    for start in range(0, len(jobs), 4):
        group = jobs[start:start + 4]
        signature = object_sha(group)
        for job in group:
            result[job['id']] = {'batch_start': start, 'ordered_ids': [j['id'] for j in group],
                                 'cohort_sha256': signature}
    return result


def branch_plan(decision):
    require(decision.get('status') == 'complete', 'Decision is not complete')
    branch, selected = decision.get('branch'), decision.get('selected')
    eligible = decision.get('eligible_ranked')
    require(isinstance(eligible, list) and len(set(eligible)) == len(eligible), 'Invalid eligible list')
    require(all(a in A_CHOICES for a in eligible), 'Unknown eligible recipe')
    if branch == 'A':
        require(eligible and selected == eligible[0], 'A selection does not match frozen ranking')
        family, control_family, target, control = A_CHOICES[selected]
        families, seed, arms, kind, jobs = (family, control_family), 2026093002, ('Base', selected, control), 'confirmation', 'confirmation18.json'
    else:
        require(branch == 'B' and selected is None and eligible == [], 'Invalid B decision')
        families, seed, target, arms, kind, jobs = ('D6', 'DX6'), 2026093001, 512, ORIGINAL_B + ('D6', 'DX6'), 'precision', 'main12.json'
    return dict(branch=branch, selected=selected, seed=seed, kind=kind, jobs=jobs,
                arms=list(arms), training=[dict(family=f, seed=seed, target=target,
                stages=[s for s in (32, 128, 512) if s <= target]) for f in families],
                bounds=[dict(cap=c, context=x) for c, x in BOUNDS])


def next_jobs(jobs, active_records, cap, floor):
    hits = {ident for records in active_records.values() for ident, record in records.items()
            if record['finish_reason'] == 'length'}
    needed = hits | {ident for ident, minimum in floor.items() if minimum > cap}
    return [job for job in jobs if job['id'] in needed]


def ensure_idle(run):
    require(not (run / 'campaign-complete.json').exists(), 'Campaign already marked complete')
    for name in ('active-process.json', 'continuation.json'):
        path = run / name
        if not path.exists():
            continue
        row = read(path)
        for key in ('pid', 'launcher_pid', 'pgid'):
            pid = row.get(key)
            if isinstance(pid, int) and pid != os.getpid():
                require(not Path(f'/proc/{pid}').exists(), f'Live process in {name}: {key}={pid}')


class Runner:
    def __init__(self, run=DEFAULT_RUN, backend=None):
        self.run = Path(run).resolve()
        self.backend = backend
        self.branch = self.run / 'branch'
        self.manifest = None
        self.initial_sources = []
        self.floor = {}
        self.artifacts = {}
        self.evidence_hash = None
        self.plan = None

    def frozen(self, path):
        path = Path(path).resolve()
        require(str(path) in self.manifest, f'Input not in frozen manifest: {path}')
        require(sha(path) == self.manifest[str(path)], f'Frozen input changed: {path}')
        return path

    def verify_manifest(self):
        self.manifest = read(self.run / 'frozen-manifest.json')['sha256']
        require(isinstance(self.manifest, dict) and self.manifest, 'Empty frozen manifest')
        for path, expected in self.manifest.items():
            require(sha(path) == expected, f'Frozen input changed: {path}')
        for name, expected in SCIENTIFIC_SOURCE_SHA256.items():
            require(sha(HERE / name) == expected, f'Committed scientific source changed: {name}')

    def barrier(self, evidence):
        """Read-only. Review content is never deserialized, only hash-bound."""
        evidence = Path(evidence).resolve()
        ready = read(evidence)
        require(ready.get('schema_version') == 1 and ready.get('status') == 'ready', 'Invalid ready receipt')
        self.verify_manifest()
        require(set(ready.get('artifacts', {})) == set(ARTIFACT_ROLES), 'Missing/unknown evidence artifact roles')
        self.artifacts = ready['artifacts']
        for role, info in self.artifacts.items():
            path = Path(info['path']).resolve()
            require(path.is_relative_to(self.run), f'Artifact outside runtime: {role}')
            require(sha(path) == info['sha256'], f'Evidence artifact hash mismatch: {role}')
        def value(role):
            return read(self.artifacts[role]['path'])
        def digest(role):
            return self.artifacts[role]['sha256']
        require(Path(self.artifacts['initial_scores']['path']).resolve() != self.run / 'scores/current.json',
                'Initial scores must be an immutable phase snapshot')
        require(Path(self.artifacts['initial_all_stages']['path']).resolve() != self.run / 'scores/all-stages.json',
                'Initial all-stages must be an immutable phase snapshot')
        for role, filename in [('frozen_manifest', 'frozen-manifest.json'), ('decision', 'decision.json'),
                               ('completion_policy', 'completion-policy.json'), ('timing_policy', 'timing-policy.json'),
                               ('gpu_priority_policy', 'gpu-priority-policy.json')]:
            require(digest(role) == sha(self.run / filename), f'Stale live evidence: {role}')
        require(value('timing_policy').get('mode') == 'complete_original_plan', 'Completion timing policy required')
        require(value('gpu_priority_policy').get('mode') == 'observe_only_user_notifies', 'Unexpected live GPU policy')
        review = value('review_completion')
        require(review.get('status') == 'complete' and all(review.get(k) is True for k in
                ('canonical', 'full_text_coverage', 'all_packets_graded')), 'Canonical full-text review incomplete')
        require(isinstance(review.get('packet_count'), int) and review['packet_count'] >= 0 and
                review['packet_count'] == review.get('graded_count'), 'Canonical grade coverage mismatch')
        for field, role in [('packet_sha256', 'review_packets'), ('mapping_sha256', 'review_mapping'),
                            ('grades_sha256', 'review_grades'), ('review_receipt_sha256', 'review_receipt')]:
            require(review.get(field) == digest(role), f'Unbound review evidence: {field}')
        execution = value('decision_execution')
        require(execution.get('status') == 'complete' and execution.get('returncode') == 0 and
                execution.get('after_canonical_grade_save') is True, 'Unverified decision execution')
        for field, role in [('decision_sha256', 'decision'), ('grades_sha256', 'review_grades'),
                            ('mapping_sha256', 'review_mapping'), ('scores_sha256', 'initial_scores'),
                            ('all_stages_sha256', 'initial_all_stages')]:
            require(execution.get(field) == digest(role), f'Stale decision execution: {field}')
        require(execution.get('decide_sha256') == SCIENTIFIC_SOURCE_SHA256['decide.py'], 'Decision driver changed')
        require(value('mechanical_audit').get('status') == 'pass', 'Initial mechanical audit has not passed')
        self.plan = branch_plan(value('decision'))
        self.validate_initial(value('initial_scores'), value('initial_all_stages'))
        self.evidence_hash = sha(evidence)
        return self.plan

    def adapter(self, arm, seed):
        if arm == 'Base':
            return None
        family, update = ({'D6': ('D6', 512), 'DX6': ('DX6', 512)}.get(arm)
                          or (('DX', 512) if arm == 'DX512' else (arm[0], int(arm[1:]))))
        return self.run / f'train/{family}-{seed}-{update}/final/adapter-vllm'

    def validate_training(self, family, seed, update):
        cfgpath = self.frozen(self.run / f'configs/{family}-{seed}-{update}.json')
        cfg = read(cfgpath)
        require(cfg['seed'] == seed and cfg['updates'] == update, 'Training config seed/update mismatch')
        dataset = self.frozen(cfg['dataset'])
        metadata = Path(cfg['model_metadata'])
        require(sha(dataset) == cfg['dataset_sha256'] and sha(metadata) == cfg['model_metadata_sha256'], 'Training input hash mismatch')
        directory = self.run / f'train/{family}-{seed}-{update}'
        receipt, final = read(directory / 'receipt.json'), read(directory / 'final/receipt.json')
        for record in (receipt, final):
            require(record.get('status') == 'complete', f'Incomplete checkpoint: {directory}')
            require(all(record.get(k) == update for k in ('global_updates', 'planned_updates', 'optimizer_step_min', 'optimizer_step_max')),
                    f'Checkpoint update/optimizer mismatch: {directory}')
            require(record.get('config_sha256') == sha(cfgpath) and record.get('dataset_sha256') == sha(dataset), 'Checkpoint input mismatch')
            require(record.get('model_revision') == cfg['model_revision'] == REVISION and
                    record.get('model_metadata_sha256') == sha(metadata), 'Checkpoint model mismatch')
            require(record.get('training_parameters') == {key: cfg[key] for key in PARAMETERS}, 'Checkpoint parameters differ')
            require(record.get('driver_sha256') == sha(self.frozen(HERE.parent / 'program-self-training-2026-09-26/train_sft.py')),
                    'Checkpoint base trainer differs')
            require(all(record.get(k) == 400 for k in ('saved_adapter_tensors_verified', 'vllm_adapter_tensors_verified',
                    'optimizer_state_entries', 'changed_lora_tensors')), 'Checkpoint tensor verification incomplete')
            require(record.get('cpu_check', {}).get('status') == 'pass', 'Checkpoint CPU check missing')
            for key, suffix in [('adapter_sha256', 'adapter/adapter_model.safetensors'),
                                ('vllm_adapter_sha256', 'adapter-vllm/adapter_model.safetensors'),
                                ('optimizer_sha256', 'optimizer.pt')]:
                require(record.get(key) == sha(directory / 'final' / suffix), f'Checkpoint artifact changed: {suffix}')
            for key, filename in [('example_order_sha256', 'example-order.json'), ('tokenization_sha256', 'tokenization.json')]:
                require(record.get(key) == sha(directory / filename), f'Checkpoint metadata changed: {filename}')
        order = read(directory / 'example-order.json')
        dataset_ids = [row['id'] for row in read(dataset)]
        require(dataset_ids and len(set(dataset_ids)) == len(dataset_ids), 'Empty/duplicate training dataset IDs')
        expected, epoch = [], 0
        while len(expected) < update * 4:
            ids = list(dataset_ids)
            random.Random(seed + epoch).shuffle(ids)
            expected.extend({'epoch': epoch, 'id': ident} for ident in ids)
            epoch += 1
        require(order == expected[:update * 4], 'Deterministic training order mismatch')
        require(receipt['processed_order_sha256'] == final['processed_order_sha256'] == object_sha(order), 'Processed order hash mismatch')
        prior_update = {32: None, 128: 32, 512: 128}[update]
        if prior_update:
            prior_dir = self.run / f'train/{family}-{seed}-{prior_update}/final'
            previous = self.validate_training(family, seed, prior_update)
            require(cfg.get('prior_checkpoint') == str(prior_dir), 'Wrong configured prior checkpoint')
            for record in (receipt, final):
                require(record.get('prior_checkpoint') == str(prior_dir) and record.get('optimizer_state_loaded') is True,
                        'Optimizer continuation not verified')
                for key in ('adapter_sha256', 'vllm_adapter_sha256', 'optimizer_sha256'):
                    require(record.get('prior_' + key) == previous[key], 'Prior checkpoint hash mismatch')
                require(previous['processed_order_sha256'] == object_sha(order[:prior_update * 4]), 'Prior order is not exact prefix')
        else:
            require(cfg.get('prior_checkpoint') is None and final.get('prior_checkpoint') is None and
                    final.get('optimizer_state_loaded') is False, 'Fresh stage is not fresh')
        return final

    def output_info(self, directory, jobs_path, arm, seed, kind, cap):
        directory, jobs_path = Path(directory), Path(jobs_path)
        jobs = read(jobs_path)
        signature = batches(jobs)
        receipt = read(directory / 'receipt.json')
        context = dict(BOUNDS).get(cap)
        require(context is not None and receipt.get('status') == 'complete', f'Incomplete/invalid output: {directory}')
        adapter = self.adapter(arm, seed)
        driver = HERE.parent / 'related-numeric-sft-2026-09-28' / ('generate_greedy.py' if kind == 'short' else 'generate_batch.py')
        expected = dict(cap=cap, context=context, batch_size=4, samples=1, enable_thinking=False,
                        jobs_sha256=sha(jobs_path), driver_sha256=sha(self.frozen(driver)), model_revision=REVISION,
                        adapter=str(adapter) if adapter else None,
                        adapter_sha256=sha(adapter / 'adapter_model.safetensors') if adapter else None,
                        temperature=0.0 if kind == 'short' else 0.7, top_p=1.0 if kind == 'short' else 0.95,
                        top_k=-1 if kind == 'short' else 20, presence_penalty=0.0 if kind == 'short' else 0.2)
        for key, value in expected.items():
            require(receipt.get(key) == value, f'Output receipt mismatch: {directory.name}:{key}')
        metadata = ROOT / 'docs/research/qwen35-self-materials-2026-09-23/model.json'
        require(receipt.get('model_metadata_sha256') == sha(metadata), 'Output model metadata changed')
        files = {p.name[:-7]: p for p in directory.glob('*-0.json')}
        require(set(files) == set(signature) and receipt.get('completed_jobs') == len(jobs), f'Output count/IDs mismatch: {directory}')
        records, hashes = {}, {}
        for job in jobs:
            ident, path = job['id'], files[job['id']]
            output = read(path)
            require(all(output.get(k) == v for k, v in job.items()), f'Output frozen job mismatch: {path.name}')
            require(not {'target', 'answer_exact'} & output.keys(), 'Answer key leaked into output')
            require(output.get('revision') == REVISION and output.get('sample') == 0 and
                    output.get('adapter') == expected['adapter'], 'Output model/sample mismatch')
            require(output.get('batch_start') == signature[ident]['batch_start'], 'Output batch_start differs')
            require(output.get('finish_reason') in ('stop', 'length') and isinstance(output.get('prompt_ids'), list) and
                    output['prompt_ids'] and len(output.get('completion_ids', [])) <= cap, 'Invalid output completion metadata')
            require(isinstance(output.get('raw_text'), str) and isinstance(output.get('final_text'), str), 'Missing complete output text')
            # Do not expose text or numeric outcomes to the operational logs.
            records[ident] = {k: output[k] for k in ('id', 'seed', 'messages', 'prompt_ids', 'batch_start', 'finish_reason')}
            hashes[ident] = sha(path)
        return dict(directory=str(directory), jobs_path=str(jobs_path), jobs=jobs, batches=signature,
                    receipt=receipt, receipt_sha256=sha(directory / 'receipt.json'), records=records, file_sha256=hashes)

    def reject_stage_duplicates(self, arm, seed, kind, cap, expected=None):
        pattern = re.compile(rf'^{re.escape(arm)}-{seed}-{re.escape(kind)}-{cap}(?:-|$)')
        dirs = [d for d in (self.run / 'outputs').glob('*') if d.is_dir() and pattern.match(d.name)]
        require(len(dirs) <= 1, f'Ambiguous same-cap output directories: {arm}/{kind}/{cap}')
        if dirs and expected is not None:
            require(dirs[0] == Path(expected), f'Unexpected same-cap output directory: {dirs[0]}')
        return dirs

    def validate_initial(self, scored_rows, all_stage_rows):
        require(isinstance(scored_rows, list), 'Initial score snapshot is not a list')
        main12 = read(self.frozen(self.run / 'jobs/main12.json'))
        main24 = read(self.frozen(self.run / 'jobs/main24.json'))
        require(len(main12) == 12 and len(main24) == 24 and main24[:12] == main12, 'Invalid frozen main jobs')
        self.initial_sources = []
        expected_final, info_cache = {}, {}
        groups = [('main', 'common', INITIAL_ARMS, main12), ('main', 'rep2', INITIAL_ARMS[:3], main24[12:]),
                  ('retention', 'all', INITIAL_ARMS, read(self.frozen(self.run / 'jobs/retention.json'))),
                  ('short', 'all', INITIAL_ARMS, read(self.frozen(self.run / 'jobs/short.json')))]
        require(len(groups[2][3]) == 4 and len(groups[3][3]) == 168, 'Invalid frozen diagnostic jobs')
        for family in ('S', 'X', 'D', 'DX'):
            self.validate_training(family, 2026093001, 512)
        for kind, group, arms, all_jobs in groups:
            active = all_jobs
            for level, (cap, _) in enumerate(BOUNDS):
                group_records = {}
                for arm in arms:
                    if level == 0:
                        jobsname = ('main24' if arm in INITIAL_ARMS[:3] else 'main12') if kind == 'main' else kind
                        jobpath = self.run / f'jobs/{jobsname}.json'
                        directory = self.run / f'outputs/{arm}-2026093001-{kind}-{cap}'
                    else:
                        jobpath = self.run / f'extensions/jobs-{kind}-{group}-{cap}.json'
                        require(read(jobpath) == active, f'Initial extension subset differs: {jobpath}')
                        directory = self.run / f'outputs/{arm}-2026093001-{kind}-{cap}-{group}'
                    if str(directory) not in info_cache:
                        info_cache[str(directory)] = self.output_info(directory, jobpath, arm, 2026093001, kind, cap)
                    info = info_cache[str(directory)]
                    group_records[arm] = {j['id']: info['records'][j['id']] for j in active}
                    for job in active:
                        ident = job['id']
                        expected_final[(arm, kind, ident)] = dict(file=str(directory / f'{ident}-0.json'),
                            file_sha256=info['file_sha256'][ident], cap=cap, finish_reason=info['records'][ident]['finish_reason'])
                self.paired(group_records)
                following = next_jobs(all_jobs, group_records, cap, {})
                if not following:
                    break
                if level == len(BOUNDS) - 1:
                    censored = read(self.run / f'extensions/censored-{kind}-{group}.json')
                    require(set(censored.get('ids', [])) == {j['id'] for j in following} and
                            censored.get('cap') == cap and censored.get('arms') == list(arms), 'Missing final censor receipt')
                    # The frozen decision uses common first-sample main and
                    # retention only. Final-bound replication is descriptive;
                    # its completed censored observations do not block a gate.
                    require(kind == 'short' or (kind == 'main' and group == 'rep2'),
                            'Initial gate comparison is censored')
                active = following
        actual = {}
        for row in scored_rows:
            require(row.get('training_seed') == 2026093001 and row.get('arm') in INITIAL_ARMS and
                    row.get('kind') in ('main', 'retention', 'short'), 'Initial snapshot contains another phase')
            key = (row['arm'], row['kind'], row['id'])
            require(key not in actual, 'Duplicate initial final score row')
            actual[key] = {k: row.get(k) for k in ('file', 'file_sha256', 'cap', 'finish_reason')}
        require(actual == expected_final, 'Initial score snapshot does not match completed common-cap replay')
        # Bind even superseded source answers before allowing precision projections.
        expected_all = {str(Path(directory) / f'{ident}-0.json'): digest
                        for directory, info in info_cache.items() for ident, digest in info['file_sha256'].items()}
        actual_all = {}
        for row in all_stage_rows:
            path = row.get('file')
            require(path not in actual_all, 'Duplicate all-stage source row')
            actual_all[path] = row.get('file_sha256')
        require(actual_all == expected_all, 'Initial all-stage source hashes differ')
        # Ensure no extra/stale initial output directory can change frozen scorer selection.
        for directory in (self.run / 'outputs').glob('*-2026093001-*'):
            parts = directory.name.split('-')
            if parts[0] in INITIAL_ARMS and parts[2] in ('main', 'short', 'retention'):
                require(str(directory) in info_cache, f'Unexpected initial output directory: {directory}')
        for directory, info in info_cache.items():
            arm, _, kind, cap, *_ = Path(directory).name.split('-')
            if kind == 'main' and arm in ORIGINAL_B:
                self.initial_sources.append(dict(arm=arm, cap=int(cap), **info))
        self.floor = {job['id']: expected_final[('Base', 'main', job['id'])]['cap'] for job in main12}

    @staticmethod
    def paired(group_records):
        references = {}
        for records in group_records.values():
            for ident, record in records.items():
                signature = {key: record[key] for key in ('seed', 'messages', 'prompt_ids', 'batch_start')}
                if ident in references:
                    require(signature == references[ident], f'Paired input differs: {ident}')
                references[ident] = signature

    def reuse_candidate(self, arm, cap, jobs):
        target = batches(jobs)
        candidates = [s for s in self.initial_sources if s['arm'] == arm and s['cap'] == cap and
                      all(ident in s['batches'] and s['batches'][ident] == sig for ident, sig in target.items())]
        require(len(candidates) <= 1, f'Ambiguous original reuse source: {arm}/{cap}')
        return candidates[0] if candidates else None

    def source_provenance(self, source, jobs):
        directory = Path(source['directory'])
        require(sha(directory / 'receipt.json') == source['receipt_sha256'], 'Original reuse receipt changed')
        files = {}
        for job in jobs:
            path = directory / f"{job['id']}-0.json"
            require(sha(path) == source['file_sha256'][job['id']], 'Original reuse output changed')
            files[job['id']] = dict(path=str(path), sha256=source['file_sha256'][job['id']])
        return dict(directory=str(directory), receipt_sha256=source['receipt_sha256'],
                    jobs_path=source['jobs_path'], jobs_sha256=sha(source['jobs_path']), files=files)

    def project(self, out, jobs_path, source, provenance):
        require(not out.exists(), f'Projection output already exists: {out}')
        # Stage under branch/, never leave a partial projection visible to score.py.
        staging = self.branch / 'projection-staging' / out.name
        require(not staging.exists(), f'Interrupted projection needs inspection: {staging}')
        staging.mkdir(parents=True)
        jobs = read(jobs_path)
        for job in jobs:
            spec = provenance['files'][job['id']]
            require(sha(spec['path']) == spec['sha256'], 'Reuse source changed during projection')
            target = staging / f"{job['id']}-0.json"
            shutil.copyfile(spec['path'], target)
            require(sha(target) == spec['sha256'], 'Projection is not byte-verbatim')
        receipt = copy.deepcopy(source['receipt'])
        for key in ('start_unix', 'end_unix'):
            receipt.pop(key, None)
        receipt.update(status='complete', jobs_sha256=sha(jobs_path), completed_jobs=len(jobs),
                       elapsed_seconds=0.0, incremental_gpu_seconds=0.0, derived_projection=True,
                       source_generation_elapsed_seconds=source['receipt'].get('elapsed_seconds'),
                       reuse_provenance=provenance)
        save_once(staging / 'receipt.json', receipt)
        out.parent.mkdir(parents=True, exist_ok=True)
        require(not out.exists(), 'Concurrent output appeared during projection')
        staging.rename(out)

    def stage_spec(self, arm, kind, jobs_path, seed, cap, context, allow_reuse=False):
        jobs = read(jobs_path)
        source = self.reuse_candidate(arm, cap, jobs) if allow_reuse else None
        mode = 'reuse' if source else 'generate'
        suffix = '-reuse-main' if source else ('' if cap == BOUNDS[0][0] else '-common')
        out = self.run / f'outputs/{arm}-{seed}-{kind}-{cap}{suffix}'
        provenance = self.source_provenance(source, jobs) if source else None
        state = dict(schema_version=1, evidence_sha256=self.evidence_hash, arm=arm, seed=seed, kind=kind,
                     cap=cap, context=context, jobs_path=str(jobs_path), jobs_sha256=sha(jobs_path),
                     batches=batches(jobs), mode=mode, output=str(out), provenance=provenance)
        planpath = self.branch / f'stages/{arm}-{seed}-{kind}-{cap}.json'
        return state, source, out, planpath

    @staticmethod
    def verify_projection(info, provenance):
        require(bool(info['receipt'].get('derived_projection')) == bool(provenance), 'Projection mode changed')
        if provenance:
            require(info['receipt'].get('elapsed_seconds') == 0 and info['receipt'].get('incremental_gpu_seconds') == 0 and
                    info['receipt'].get('reuse_provenance') == provenance, 'Projection receipt changed')
            require(info['file_sha256'] == {ident: spec['sha256'] for ident, spec in provenance['files'].items()},
                    'Projection source/destination hash differs')

    @staticmethod
    def completion_info(info, planpath):
        return dict(stage_plan_sha256=sha(planpath), receipt_sha256=info['receipt_sha256'], files=info['file_sha256'])

    def stage(self, arm, kind, jobs_path, seed, cap, context, allow_reuse=False):
        state, source, out, planpath = self.stage_spec(arm, kind, jobs_path, seed, cap, context, allow_reuse)
        provenance = state['provenance']
        self.reject_stage_duplicates(arm, seed, kind, cap, out)
        if out.exists():
            require(planpath.exists(), f'Output lacks managed stage plan: {out}')
        save_once(planpath, state)
        if not out.exists():
            if source:
                self.project(out, jobs_path, source, provenance)
            else:
                suffix = '' if cap == BOUNDS[0][0] else '-common'
                self.backend.generate(arm, kind, jobs_path, seed=seed, cap=cap, context=context, suffix=suffix)
        self.reject_stage_duplicates(arm, seed, kind, cap, out)
        info = self.output_info(out, jobs_path, arm, seed, kind, cap)
        self.verify_projection(info, provenance)
        save_once(planpath.with_name(planpath.stem + '-complete.json'), self.completion_info(info, planpath))
        return info

    def execute(self):
        require(self.plan is not None and self.evidence_hash, 'Execute requires validated pre-branch evidence')
        require(self.backend is not None, 'Guarded backend is not installed')
        ensure_idle(self.run)
        self.branch.mkdir(parents=True, exist_ok=True)
        with (self.branch / 'runner.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise EvidenceError('Another branch runner holds the exclusive operational lock') from exc
            self.check_scope()
            return self._execute_locked()

    def check_scope(self):
        """Do not let pre-existing extra branch conditions enter frozen scoring."""
        allowed_training = {f'{family}-2026093001-{step}' for family in ('S', 'X', 'D', 'DX')
                            for step in (32, 128, 512)}
        allowed_training.update(f"{t['family']}-{t['seed']}-{step}" for t in self.plan['training'] for step in t['stages'])
        for directory in (self.run / 'train').glob('*'):
            if directory.is_dir():
                require(directory.name in allowed_training, f'Unexpected training condition: {directory.name}')
                family, seed, update = directory.name.rsplit('-', 2)
                # Validate later/existing chains before launching even an earlier
                # missing stage of another family. A broken chain is not a reason
                # to generate replacement prerequisites speculatively.
                self.validate_training(family, int(seed), int(update))
        branch_outputs = set()
        for directory in (self.run / 'outputs').glob('*'):
            require(directory.is_dir(), f'Unexpected file in outputs: {directory.name}')
            parts = directory.name.split('-')
            require(len(parts) >= 4, f'Unrecognized output directory: {directory.name}')
            arm, seed, kind, cap = parts[:4]
            require(cap in {str(c) for c, _ in BOUNDS}, f'Unregistered output cap: {directory.name}')
            if kind in ('main', 'retention', 'short'):
                require(arm in INITIAL_ARMS and seed == '2026093001', 'Unexpected initial condition')
            else:
                require(kind == self.plan['kind'] and arm in self.plan['arms'] and seed == str(self.plan['seed']),
                        f'Output from another branch/condition: {directory.name}')
                cap, seed = int(cap), int(seed)
                jobs_path = (self.run / 'jobs' / self.plan['jobs'] if cap == BOUNDS[0][0] else
                             self.run / f'extensions/jobs-{kind}-common-{cap}.json')
                planpath = self.branch / f'stages/{arm}-{seed}-{kind}-{cap}.json'
                require(planpath.exists(), f'Output lacks managed stage plan: {directory}')
                state, _, expected_out, _ = self.stage_spec(arm, kind, jobs_path, seed, cap, dict(BOUNDS)[cap],
                                        allow_reuse=self.plan['branch'] == 'B' and arm in ORIGINAL_B)
                require(directory == expected_out and read(planpath) == state, 'Stale or mismatched managed stage plan')
                self.reject_stage_duplicates(arm, seed, kind, cap, directory)
                info = self.output_info(directory, jobs_path, arm, seed, kind, cap)
                self.verify_projection(info, state['provenance'])
                completion = read(planpath.with_name(planpath.stem + '-complete.json'))
                require(completion == self.completion_info(info, planpath), 'Managed stage completion/hash differs')
                branch_outputs.add(str(directory))
        return branch_outputs

    def _execute_locked(self):
        save_once(self.branch / 'launch.json', dict(schema_version=1, evidence_sha256=self.evidence_hash,
                  runner_sha256=sha(__file__), scientific_source_sha256=SCIENTIFIC_SOURCE_SHA256,
                  plan=self.plan, artifacts=self.artifacts))
        plan = self.plan
        for training in plan['training']:
            family, seed = training['family'], training['seed']
            for step in training['stages']:
                self.frozen(self.run / f'configs/{family}-{seed}-{step}.json')
                out = self.run / f'train/{family}-{seed}-{step}'
                if not out.exists():
                    self.backend.train(family, seed=seed, target=step)
                self.validate_training(family, seed, step)
        jobs_path = self.frozen(self.run / 'jobs' / plan['jobs'])
        all_jobs = read(jobs_path)
        require(len(all_jobs) == (18 if plan['branch'] == 'A' else 12), 'Branch job count differs')
        floor = self.floor if plan['branch'] == 'B' else {}
        if floor:
            save_once(self.branch / 'main-final-cap-floor.json', dict(evidence_sha256=self.evidence_hash, caps=floor))
        final = {arm: {} for arm in plan['arms']}
        active, censored, visited = all_jobs, [], set()
        for index, (cap, context) in enumerate(BOUNDS):
            if index:
                jobs_path = self.run / f"extensions/jobs-{plan['kind']}-common-{cap}.json"
                save_once(jobs_path, active)
            current = {}
            for arm in plan['arms']:
                info = self.stage(arm, plan['kind'], jobs_path, plan['seed'], cap, context,
                                  allow_reuse=plan['branch'] == 'B' and arm in ORIGINAL_B)
                visited.add(info['directory'])
                current[arm] = info['records']
                for ident, record in info['records'].items():
                    final[arm][ident] = dict(cap=cap, finish_reason=record['finish_reason'],
                        file=str(Path(info['directory']) / f'{ident}-0.json'), file_sha256=info['file_sha256'][ident])
            self.paired(current)
            following = next_jobs(all_jobs, current, cap, floor)
            if not following:
                break
            if index == len(BOUNDS) - 1:
                censored = [j['id'] for j in following]
                save_once(self.branch / f"censored-{plan['kind']}-common.json", dict(ids=censored, cap=cap, arms=plan['arms']))
                break
            active = following
        require(self.check_scope() == visited, 'Unvisited branch output would alter scorer common caps')
        expected = {j['id'] for j in all_jobs}
        for arm, rows in final.items():
            require(set(rows) == expected, f'Incomplete final branch arm: {arm}')
        for ident in expected:
            caps = {final[arm][ident]['cap'] for arm in plan['arms']}
            require(len(caps) == 1 and next(iter(caps)) >= floor.get(ident, 0), 'Unequal final caps or below initial floor')
        result = dict(status='censored' if censored else 'generation_complete', branch=plan['branch'],
                      kind=plan['kind'], seed=plan['seed'], expected_per_arm=len(all_jobs),
                      censored_ids=censored, evidence_sha256=self.evidence_hash, final=final,
                      next='Frozen score.py branch packet, full-text review, supplemental/mechanical audit, report')
        save_once(self.branch / 'generation-complete.json', result)
        return {k: v for k, v in result.items() if k != 'final'}


def install_backend():
    # Import order is operationally significant: resume replaces campaign.run_gpu.
    import resume
    resume.install_shutdown_handlers()
    import campaign
    require(campaign.run_gpu is resume.wait_and_run, 'GPU wait/priority wrapper not installed')
    return campaign


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    require(not args.execute or args.evidence is not None, '--execute requires --evidence')
    if args.evidence is None:
        result = dict(status='plan_only', branch_selected=None,
                      A={choice: branch_plan(dict(status='complete', branch='A', selected=choice, eligible_ranked=[choice]))
                         for choice in A_CHOICES},
                      B=branch_plan(dict(status='complete', branch='B', selected=None, eligible_ranked=[])),
                      next='Complete canonical review and unchanged decide.py; supply the documented ready receipt.')
    else:
        runner = Runner()
        plan = runner.barrier(args.evidence)
        if args.execute:
            runner.backend = install_backend()
            result = runner.execute()
        else:
            result = dict(status='plan_only_evidence_verified', plan=plan, evidence_sha256=runner.evidence_hash)
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    try:
        main()
    except (EvidenceError, KeyError, TypeError, ValueError) as error:
        print(json.dumps(dict(status='refused', error=str(error))), file=sys.stderr)
        raise SystemExit(2)
