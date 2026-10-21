"""CPU-only branch orchestration tests; fake backend never imports a GPU engine."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import random
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1] / 'docs/research/night-recipe-search-2026-09-29'
spec = importlib.util.spec_from_file_location('night_branch_runner', HERE / 'branch_runner.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return path


def decision(selected=None):
    return dict(status='complete', branch='A' if selected else 'B', selected=selected,
                eligible_ranked=[selected] if selected else [])


class Fixture:
    def __init__(self, root):
        self.run = Path(root)
        self.run.mkdir(exist_ok=True)
        self.train_calls, self.generation_calls = [], []
        self.hits = {}
        self.model = b.ROOT / 'docs/research/qwen35-self-materials-2026-09-23/model.json'
        self.drivers = [HERE / 'decide.py',
            HERE.parent / 'program-self-training-2026-09-26/train_sft.py',
            HERE.parent / 'related-numeric-sft-2026-09-28/generate_batch.py',
            HERE.parent / 'related-numeric-sft-2026-09-28/generate_greedy.py']
        self.main12 = [self.job(f'q{i:02d}', i) for i in range(12)]
        self.main24 = self.main12 + [self.job(f'q{i:02d}-s2', 100+i, replicate=2) for i in range(12)]
        self.confirm = [self.job(f'confirm{i}', 200+i) for i in range(18)]
        for name, jobs in [('main12', self.main12), ('main24', self.main24), ('confirmation18', self.confirm),
                           ('retention', [self.job(f'r{i}', 400+i) for i in range(4)]),
                           ('short', [self.job(f's{i}', 500+i) for i in range(168)])]:
            write(self.run / f'jobs/{name}.json', jobs)
        for family in ('S', 'X', 'D', 'DX', 'D6', 'DX6'):
            data = write(self.run / f'data/{family}.json', [dict(id='a'), dict(id='b'), dict(id='c')])
            for seed in (2026093001, 2026093002):
                for step in (32, 128, 512):
                    cfg = dict(dataset=str(data), dataset_sha256=b.sha(data), model_metadata=str(self.model),
                        model_metadata_sha256=b.sha(self.model), model_revision=b.REVISION, updates=step, seed=seed,
                        learning_rate=5e-6, grad_accumulation=4, grad_clip=1.0, lora_rank=8, lora_alpha=16,
                        lora_modules=['mock_module'], ce_chunk_tokens=64, max_target_tokens=4096,
                        max_sequence_tokens=8192, enable_thinking=False)
                    if step > 32:
                        cfg['prior_checkpoint'] = str(self.run / f'train/{family}-{seed}-{32 if step == 128 else 128}/final')
                    write(self.run / f'configs/{family}-{seed}-{step}.json', cfg)
        files = list((self.run / 'jobs').glob('*.json')) + list((self.run / 'configs').glob('*.json')) + list((self.run / 'data').glob('*.json')) + self.drivers[1:]
        write(self.run / 'frozen-manifest.json', dict(sha256={str(p): b.sha(p) for p in files}))
        write(self.run / 'completion-policy.json', dict(scope='complete original finite plan'))
        write(self.run / 'timing-policy.json', dict(mode='complete_original_plan'))
        write(self.run / 'gpu-priority-policy.json', dict(mode='observe_only_user_notifies'))
        self.runner = b.Runner(self.run, backend=self)
        self.runner.verify_manifest()

    @staticmethod
    def job(ident, seed, replicate=1):
        return dict(id=ident, source_id=ident, replicate=replicate, seed=seed,
                    messages=[dict(role='user', content='Synthetic CPU fixture '+ident)])

    def train(self, family, seed=2026093001, target=512):
        self.train_calls.append((family, seed, target))
        for step in (32, 128, 512):
            if step <= target and not (self.run / f'train/{family}-{seed}-{step}').exists():
                self.make_training(family, seed, step)

    def make_training(self, family, seed, step):
        directory = self.run / f'train/{family}-{seed}-{step}'
        cfgpath = self.run / f'configs/{family}-{seed}-{step}.json'
        cfg = b.read(cfgpath)
        prior = b.read(Path(cfg['prior_checkpoint']) / 'receipt.json') if step > 32 else None
        order, epoch = [], 0
        while len(order) < step * 4:
            ids = ['a', 'b', 'c']
            random.Random(seed + epoch).shuffle(ids)
            order.extend(dict(epoch=epoch, id=i) for i in ids)
            epoch += 1
        order = order[:step * 4]
        write(directory / 'example-order.json', order)
        write(directory / 'tokenization.json', [])
        hashes = {}
        for key, path in [('adapter_sha256', 'adapter/adapter_model.safetensors'),
                          ('vllm_adapter_sha256', 'adapter-vllm/adapter_model.safetensors'),
                          ('optimizer_sha256', 'optimizer.pt')]:
            artifact = directory / 'final' / path
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(f'CPU MOCK {family} {seed} {step} {path}'.encode())
            hashes[key] = b.sha(artifact)
        receipt = dict(status='complete', global_updates=step, planned_updates=step,
            optimizer_step_min=step, optimizer_step_max=step, config_sha256=b.sha(cfgpath),
            dataset_sha256=cfg['dataset_sha256'], model_metadata_sha256=cfg['model_metadata_sha256'],
            model_revision=b.REVISION, driver_sha256=b.sha(self.drivers[1]),
            training_parameters={key: cfg[key] for key in b.PARAMETERS}, saved_adapter_tensors_verified=400,
            vllm_adapter_tensors_verified=400, optimizer_state_entries=400, changed_lora_tensors=400,
            cpu_check=dict(status='pass'), example_order_sha256=b.sha(directory/'example-order.json'),
            tokenization_sha256=b.sha(directory/'tokenization.json'), processed_order_sha256=b.object_sha(order),
            prior_checkpoint=cfg.get('prior_checkpoint'), optimizer_state_loaded=prior is not None, **hashes)
        if prior:
            receipt.update({'prior_'+key: prior[key] for key in hashes})
        write(directory / 'receipt.json', receipt)
        write(directory / 'final/receipt.json', receipt)

    def generate(self, arm, kind, jobs, seed=2026093001, cap=32768, context=40960, suffix=''):
        self.generation_calls.append((arm, kind, str(jobs), seed, cap, context, suffix))
        return self.make_output(arm, kind, jobs, seed, cap, context, suffix)

    def make_output(self, arm, kind, jobs_path, seed=2026093001, cap=32768, context=40960, suffix=''):
        out = self.run / f'outputs/{arm}-{seed}-{kind}-{cap}{suffix}'
        out.mkdir(parents=True)
        jobs = b.read(jobs_path)
        adapter = self.runner.adapter(arm, seed)
        receipt = dict(status='complete', jobs_sha256=b.sha(jobs_path), cap=cap, context=context,
            batch_size=4, samples=1, enable_thinking=False, model_revision=b.REVISION,
            driver_sha256=b.sha(self.drivers[3 if kind == 'short' else 2]),
            model_metadata_sha256=b.sha(self.model), adapter=str(adapter) if adapter else None,
            adapter_sha256=b.sha(adapter / 'adapter_model.safetensors') if adapter else None,
            temperature=0.0 if kind == 'short' else 0.7, top_p=1.0 if kind == 'short' else 0.95,
            top_k=-1 if kind == 'short' else 20, presence_penalty=0.0 if kind == 'short' else 0.2,
            completed_jobs=len(jobs), elapsed_seconds=12.5)
        write(out / 'receipt.json', receipt)
        for i, job in enumerate(jobs):
            write(out / f"{job['id']}-0.json", dict(job, revision=b.REVISION, adapter=receipt['adapter'],
                  sample=0, prompt_ids=[1, job['seed'], 3], batch_start=i-i%4,
                  completion_ids=[123], raw_text='mock output', final_text='mock output',
                  finish_reason='length' if job['id'] in self.hits.get((arm, cap), set()) else 'stop'))
        return out

    def branch(self, selected=None):
        self.runner.plan = b.branch_plan(decision(selected))
        self.runner.evidence_hash = 'f' * 64
        return self.runner

    def original_b(self, cap=32768, jobs=None):
        for family in ('D', 'DX'):
            self.train(family)
        sources = []
        for arm in b.ORIGINAL_B:
            if cap == 32768:
                path = self.run / ('jobs/main24.json' if arm == 'Base' else 'jobs/main12.json')
            else:
                path = write(self.run / f'extensions/jobs-main-common-{cap}.json', jobs)
            out = self.make_output(arm, 'main', path, cap=cap, context=dict(b.BOUNDS)[cap], suffix='' if cap == 32768 else '-common')
            sources.append(dict(arm=arm, cap=cap, **self.runner.output_info(out, path, arm, 2026093001, 'main', cap)))
        self.runner.initial_sources.extend(sources)
        self.runner.floor = {j['id']: cap if jobs and j in jobs else 32768 for j in self.main12}
        self.train_calls.clear()
        return sources

    def initial(self):
        for family in ('S', 'X', 'D', 'DX'):
            self.train(family)
        final = []
        for arm in b.INITIAL_ARMS:
            for kind in ('main', 'retention', 'short'):
                name = ('main24' if arm in b.INITIAL_ARMS[:3] else 'main12') if kind == 'main' else kind
                path = self.run / f'jobs/{name}.json'
                out = self.make_output(arm, kind, path)
                for job in b.read(path):
                    file = out / f"{job['id']}-0.json"
                    final.append(dict(arm=arm, kind=kind, training_seed=2026093001, id=job['id'],
                                      file=str(file), file_sha256=b.sha(file), cap=32768,
                                      finish_reason=b.read(file)['finish_reason']))
        return final

    def evidence(self, selected=None, rows=None):
        rows = [] if rows is None else rows
        artifact_paths = {}
        for role in b.ARTIFACT_ROLES:
            names = {'frozen_manifest': 'frozen-manifest.json', 'completion_policy': 'completion-policy.json',
                     'timing_policy': 'timing-policy.json', 'gpu_priority_policy': 'gpu-priority-policy.json',
                     'decision': 'decision.json'}
            artifact_paths[role] = self.run / names.get(role, f'evidence/{role}.json')
        for role in ('review_packets', 'review_mapping', 'review_grades', 'review_receipt'):
            write(artifact_paths[role], ['opaque hashed review fixture, never parsed by runner'])
        write(artifact_paths['decision'], decision(selected))
        write(artifact_paths['initial_scores'], rows)
        write(artifact_paths['initial_all_stages'], rows)
        write(artifact_paths['mechanical_audit'], dict(status='pass'))
        review = dict(status='complete', canonical=True, full_text_coverage=True, all_packets_graded=True,
                      packet_count=1, graded_count=1)
        for field, role in [('packet_sha256', 'review_packets'), ('mapping_sha256', 'review_mapping'),
                            ('grades_sha256', 'review_grades'), ('review_receipt_sha256', 'review_receipt')]:
            review[field] = b.sha(artifact_paths[role])
        write(artifact_paths['review_completion'], review)
        execution = dict(status='complete', returncode=0, after_canonical_grade_save=True, decide_sha256=b.sha(HERE/'decide.py'))
        for field, role in [('decision_sha256', 'decision'), ('grades_sha256', 'review_grades'),
                            ('mapping_sha256', 'review_mapping'), ('scores_sha256', 'initial_scores'),
                            ('all_stages_sha256', 'initial_all_stages')]:
            execution[field] = b.sha(artifact_paths[role])
        write(artifact_paths['decision_execution'], execution)
        return write(self.run / 'branch-ready.json', dict(schema_version=1, status='ready',
            artifacts={role: dict(path=str(p), sha256=b.sha(p)) for role, p in artifact_paths.items()}))


class BranchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.f = Fixture(self.temp.name)
        self.r = self.f.runner

    def test_default_plan_has_no_backend_import_or_writes(self):
        before = sorted(str(p) for p in self.f.run.rglob('*'))
        with mock.patch.object(b, 'install_backend') as install, contextlib.redirect_stdout(io.StringIO()):
            result = b.main([])
        install.assert_not_called()
        self.assertIsNone(result['branch_selected'])
        self.assertEqual(before, sorted(str(p) for p in self.f.run.rglob('*')))
        with self.assertRaisesRegex(b.EvidenceError, 'requires --evidence'):
            b.main(['--execute'])

    def test_backend_install_requires_resume_wrapper_and_shutdown_handlers(self):
        wait = mock.Mock()
        resume = types.SimpleNamespace(wait_and_run=wait, install_shutdown_handlers=mock.Mock())
        campaign = types.SimpleNamespace(run_gpu=wait)
        with mock.patch.dict(sys.modules, {'resume': resume, 'campaign': campaign}):
            self.assertIs(b.install_backend(), campaign)
            resume.install_shutdown_handlers.assert_called_once()
            campaign.run_gpu = mock.Mock()
            with self.assertRaisesRegex(b.EvidenceError, 'wrapper not installed'):
                b.install_backend()

    def test_exact_a_training_and_arms_for_every_selection(self):
        for selected, families, steps, arms in [('S128', ['S', 'X'], [32, 128], ['Base', 'S128', 'X128']),
              ('S512', ['S', 'X'], [32, 128, 512], ['Base', 'S512', 'X512']),
              ('D512', ['D', 'DX'], [32, 128, 512], ['Base', 'D512', 'DX512'])]:
            plan = b.branch_plan(decision(selected))
            self.assertEqual(plan['arms'], arms)
            self.assertEqual([t['family'] for t in plan['training']], families)
            self.assertTrue(all(t['stages'] == steps and t['seed'] == 2026093002 for t in plan['training']))
        with self.assertRaises(b.EvidenceError):
            b.branch_plan(dict(status='complete', branch='A', selected='S128', eligible_ranked=['D512', 'S128']))

    def test_incomplete_invalid_and_fishing_decisions_rejected(self):
        for record in [dict(status='running'), dict(status='complete', branch='C', selected=None, eligible_ranked=[]),
                       dict(status='complete', branch='B', selected='D512', eligible_ranked=[]),
                       dict(status='complete', branch='B', selected=None, eligible_ranked=['S128']),
                       dict(status='complete', branch='A', selected='D6', eligible_ranked=['D6'])]:
            with self.assertRaises(b.EvidenceError):
                b.branch_plan(record)

    def test_a_execute_all18_and_resume_is_idempotent(self):
        runner = self.f.branch('S128')
        result = runner.execute()
        self.assertEqual(result['status'], 'generation_complete')
        self.assertEqual(self.f.train_calls, [('S', 2026093002, 32), ('S', 2026093002, 128),
                                              ('X', 2026093002, 32), ('X', 2026093002, 128)])
        self.assertEqual([c[0] for c in self.f.generation_calls], ['Base', 'S128', 'X128'])
        self.assertTrue(all(len(b.read(c[2])) == 18 and c[3] == 2026093002 for c in self.f.generation_calls))
        self.f.train_calls.clear(); self.f.generation_calls.clear()
        self.assertEqual(runner.execute(), result)
        self.assertEqual(self.f.train_calls, [])
        self.assertEqual(self.f.generation_calls, [])

    def test_a_common_cap_union_and_order(self):
        self.f.hits = {('Base', 32768): {'confirm5'}, ('S128', 32768): {'confirm1'}}
        self.f.branch('S128').execute()
        high = [c for c in self.f.generation_calls if c[4] == 81920]
        self.assertEqual([c[0] for c in high], ['Base', 'S128', 'X128'])
        self.assertTrue(all([j['id'] for j in b.read(c[2])] == ['confirm1', 'confirm5'] for c in high))
        self.assertTrue(all(c[-1] == '-common' and c[5] == 98304 for c in high))

    def test_b_exact_training_two_new_initial_runs_and_byte_reuse(self):
        sources = self.f.original_b()
        runner = self.f.branch()
        result = runner.execute()
        self.assertEqual(result['expected_per_arm'], 12)
        self.assertEqual(self.f.train_calls, [(f, 2026093001, s) for f in ('D6', 'DX6') for s in (32, 128, 512)])
        self.assertEqual([c[0] for c in self.f.generation_calls], ['D6', 'DX6'])
        for source in sources:
            out = self.f.run / f"outputs/{source['arm']}-2026093001-precision-32768-reuse-main"
            receipt = b.read(out/'receipt.json')
            self.assertEqual(receipt['completed_jobs'], 12)
            self.assertEqual(receipt['elapsed_seconds'], 0)
            self.assertTrue(receipt['derived_projection'])
            for job in self.f.main12:
                self.assertEqual(b.sha(out/f"{job['id']}-0.json"), source['file_sha256'][job['id']])
        self.assertEqual(len(list((self.f.run/'outputs/Base-2026093001-precision-32768-reuse-main').glob('*-0.json'))), 12)

    def test_b_preserves_floor_even_without_new_length_hits(self):
        self.f.original_b()
        self.f.original_b(81920, [self.f.main12[7], self.f.main12[9]])
        self.f.branch().execute()
        high = [c for c in self.f.generation_calls if c[4] == 81920]
        self.assertEqual([c[0] for c in high], ['D6', 'DX6'])
        self.assertTrue(all([j['id'] for j in b.read(c[2])] == ['q07', 'q09'] for c in high))
        final = b.read(self.f.run/'branch/generation-complete.json')['final']
        self.assertTrue(all(rows['q07']['cap'] == 81920 for rows in final.values()))

    def test_new_hit_changes_cohort_and_regenerates_original_three(self):
        self.f.original_b()
        self.f.original_b(81920, [self.f.main12[7], self.f.main12[9]])
        self.f.hits[('D6', 32768)] = {'q00'}
        self.f.branch().execute()
        high = [c for c in self.f.generation_calls if c[4] == 81920]
        self.assertEqual([c[0] for c in high], ['Base', 'D512', 'DX512', 'D6', 'DX6'])
        self.assertTrue(all([j['id'] for j in b.read(c[2])] == ['q00', 'q07', 'q09'] for c in high))
        self.assertFalse(list((self.f.run/'outputs').glob('*precision-81920-reuse-main')))

    def test_same_batch_start_is_not_same_cohort(self):
        self.f.original_b()
        self.assertIsNotNone(self.r.reuse_candidate('Base', 32768, self.f.main12))
        self.assertIsNone(self.r.reuse_candidate('Base', 32768, self.f.main12[:2]))
        changed = copy.deepcopy(self.f.main12); changed[0]['seed'] += 1
        self.assertIsNone(self.r.reuse_candidate('Base', 32768, changed))

    def test_same_cap_duplicate_is_rejected_before_generation(self):
        for suffix in ('-one', '-two'):
            (self.f.run/f'outputs/Base-2026093002-confirmation-32768{suffix}').mkdir(parents=True)
        with self.assertRaisesRegex(b.EvidenceError, 'Ambiguous same-cap'):
            self.r.reject_stage_duplicates('Base', 2026093002, 'confirmation', 32768)
        self.assertEqual(self.f.generation_calls, [])

    def test_projection_hash_drift_rejected_on_resume(self):
        self.f.original_b()
        runner = self.f.branch(); runner.execute()
        out = self.f.run/'outputs/Base-2026093001-precision-32768-reuse-main/q00-0.json'
        row = b.read(out); row['raw_text'] = 'changed'; write(out, row)
        with self.assertRaisesRegex(b.EvidenceError, 'source/destination hash differs'):
            runner.execute()

    def test_generated_hash_drift_rejected_on_resume(self):
        runner = self.f.branch('S128'); runner.execute()
        out = self.f.run/'outputs/Base-2026093002-confirmation-32768/confirm0-0.json'
        row = b.read(out); row['raw_text'] = 'changed'; write(out, row)
        self.f.generation_calls.clear()
        with self.assertRaisesRegex(b.EvidenceError, 'Managed stage completion/hash differs'):
            runner.execute()
        self.assertEqual(self.f.generation_calls, [])

    def test_incomplete_generation_receipt_refused(self):
        jobs = self.f.run/'jobs/confirmation18.json'
        out = self.f.make_output('Base', 'confirmation', jobs, 2026093002)
        receipt = b.read(out/'receipt.json'); receipt['status'] = 'running'; write(out/'receipt.json', receipt)
        with self.assertRaisesRegex(b.EvidenceError, 'Incomplete/invalid output'):
            self.r.output_info(out, jobs, 'Base', 2026093002, 'confirmation', 32768)

    def test_unmanaged_existing_output_refused(self):
        self.f.make_output('Base', 'confirmation', self.f.run/'jobs/confirmation18.json', 2026093002)
        self.r.evidence_hash = 'f'*64
        with self.assertRaisesRegex(b.EvidenceError, 'lacks managed stage plan'):
            self.r.stage('Base', 'confirmation', self.f.run/'jobs/confirmation18.json', 2026093002, 32768, 40960)

    def test_final_bound_is_censored_and_no_fourth_cap(self):
        self.f.hits = {('Base', cap): {'confirm2'} for cap, _ in b.BOUNDS}
        result = self.f.branch('S128').execute()
        self.assertEqual(result['status'], 'censored')
        self.assertEqual(result['censored_ids'], ['confirm2'])
        self.assertEqual(sorted({c[4] for c in self.f.generation_calls}), [32768, 81920, 131072])
        self.assertEqual(len(self.f.generation_calls), 9)

    def test_stage_plan_and_jobs_changes_rejected(self):
        path = self.f.run/'extensions/test.json'
        b.save_once(path, self.f.main12[:2]); b.save_once(path, self.f.main12[:2])
        with self.assertRaises(b.EvidenceError):
            b.save_once(path, self.f.main12[:3])

    def test_extra_branch_condition_refused_before_any_training(self):
        (self.f.run/'outputs/D6-2026093001-precision-32768').mkdir(parents=True)
        with self.assertRaisesRegex(b.EvidenceError, 'another branch/condition'):
            self.f.branch('S128').execute()
        self.assertEqual(self.f.train_calls, [])

    def test_existing_live_launcher_or_branch_lock_prevents_gpu_work(self):
        runner = self.f.branch('S128')
        active = write(self.f.run/'active-process.json', dict(pid=b.os.getppid()))
        with self.assertRaisesRegex(b.EvidenceError, 'Live process'):
            runner.execute()
        active.unlink()
        path = self.f.run/'branch/runner.lock'; path.parent.mkdir()
        with path.open('a') as lock:
            b.fcntl.flock(lock, b.fcntl.LOCK_EX | b.fcntl.LOCK_NB)
            with self.assertRaisesRegex(b.EvidenceError, 'exclusive operational lock'):
                runner.execute()
        self.assertEqual(self.f.train_calls, [])

    def test_later_scientific_sources_committed_without_false_manifest_membership(self):
        self.assertNotIn(str(HERE/'decide.py'), self.r.manifest)
        self.r.verify_manifest()
        with mock.patch.dict(b.SCIENTIFIC_SOURCE_SHA256, {'decide.py': '0'*64}):
            with self.assertRaisesRegex(b.EvidenceError, 'Committed scientific source changed'):
                self.r.verify_manifest()

    def test_optimizer_hash_and_loaded_flag_checked(self):
        self.f.train('S', 2026093002, 128)
        self.r.validate_training('S', 2026093002, 128)
        final = self.f.run/'train/S-2026093002-128/final'
        receipt = b.read(final/'receipt.json'); receipt['optimizer_state_loaded'] = False; write(final/'receipt.json', receipt)
        with self.assertRaisesRegex(b.EvidenceError, 'Optimizer continuation'):
            self.r.validate_training('S', 2026093002, 128)
        receipt['optimizer_state_loaded'] = True; write(final/'receipt.json', receipt)
        (final/'optimizer.pt').write_bytes(b'changed')
        with self.assertRaisesRegex(b.EvidenceError, 'Checkpoint artifact changed'):
            self.r.validate_training('S', 2026093002, 128)

    def test_order_prefix_and_config_hash_checked(self):
        self.f.train('S', 2026093002, 128)
        directory = self.f.run/'train/S-2026093002-128'
        order = b.read(directory/'example-order.json'); order[0]['id'] = 'wrong'; write(directory/'example-order.json', order)
        for path in (directory/'receipt.json', directory/'final/receipt.json'):
            row = b.read(path); row['example_order_sha256'] = b.sha(directory/'example-order.json'); write(path, row)
        with self.assertRaisesRegex(b.EvidenceError, 'Deterministic training order'):
            self.r.validate_training('S', 2026093002, 128)
        cfg = self.f.run/'configs/S-2026093002-128.json'
        row = b.read(cfg); row['seed'] += 1; write(cfg, row)
        with self.assertRaisesRegex(b.EvidenceError, 'Frozen input changed'):
            self.r.validate_training('S', 2026093002, 128)

    def test_failed_checkpoint_never_silently_retried(self):
        (self.f.run/'train/S-2026093002-32').mkdir(parents=True)
        with self.assertRaises(b.EvidenceError):
            self.f.branch('S128').execute()
        self.assertEqual(self.f.train_calls, [])

    def test_broken_later_existing_chain_refuses_before_other_family_training(self):
        self.f.train('X', 2026093002, 128)
        self.f.train_calls.clear()
        (self.f.run/'train/X-2026093002-128/final/optimizer.pt').write_bytes(b'corrupt')
        with self.assertRaisesRegex(b.EvidenceError, 'Checkpoint artifact changed'):
            self.f.branch('S128').execute()
        self.assertEqual(self.f.train_calls, [])

    def test_backend_failure_propagates_without_retry(self):
        runner = self.f.branch('S128')
        with mock.patch.object(self.f, 'train', side_effect=RuntimeError('simulated failure')) as training:
            with self.assertRaisesRegex(RuntimeError, 'simulated failure'):
                runner.execute()
        training.assert_called_once_with('S', seed=2026093002, target=32)

    def test_recovery_after_complete_first_stage_skips_gpu(self):
        runner = self.f.branch('S128')
        original = self.f.generate
        def interrupted(*args, **kwargs):
            if args[0] == 'S128':
                raise RuntimeError('interruption before second output')
            return original(*args, **kwargs)
        with mock.patch.object(self.f, 'generate', side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                runner.execute()
        self.f.train_calls.clear(); self.f.generation_calls.clear()
        runner.execute()
        self.assertEqual(self.f.train_calls, [])
        self.assertEqual([c[0] for c in self.f.generation_calls], ['S128', 'X128'])

    def test_barrier_rejects_missing_stale_hash_and_unreviewed_evidence(self):
        path = self.f.evidence()
        with mock.patch.object(self.r, 'validate_initial') as validate:
            self.r.barrier(path)
        validate.assert_called_once()
        review = self.f.run/'evidence/review_completion.json'
        row = b.read(review); row['all_packets_graded'] = False; write(review, row)
        with self.assertRaisesRegex(b.EvidenceError, 'artifact hash mismatch'):
            self.r.barrier(path)
        ready = b.read(path); ready['artifacts']['review_completion']['sha256'] = b.sha(review); write(path, ready)
        with self.assertRaisesRegex(b.EvidenceError, 'full-text review incomplete'):
            self.r.barrier(path)

    def test_evidence_helper_only_hashes_exact_supplied_artifacts(self):
        path = self.f.evidence()
        original = b.read(path)
        generated = b.evidence_record({role: item['path'] for role, item in original['artifacts'].items()})
        self.assertEqual(generated, original)
        with self.assertRaisesRegex(b.EvidenceError, 'artifact roles'):
            b.evidence_record({'decision': self.f.run/'decision.json'})

    def test_unmanaged_higher_cap_output_rejected_before_training(self):
        jobs = write(self.f.run/'extensions/jobs-confirmation-common-81920.json', self.f.confirm[:1])
        self.f.make_output('Base', 'confirmation', jobs, seed=2026093002, cap=81920, context=98304, suffix='-common')
        with self.assertRaisesRegex(b.EvidenceError, 'lacks managed stage plan'):
            self.f.branch('S128').execute()
        self.assertEqual(self.f.train_calls, [])
        self.assertEqual(self.f.generation_calls, [])

    def test_managed_unreachable_higher_cap_cannot_complete(self):
        runner = self.f.branch('S128'); runner.execute()
        jobs = write(self.f.run/'extensions/jobs-confirmation-common-81920.json', self.f.confirm[:1])
        runner.stage('Base', 'confirmation', jobs, 2026093002, 81920, 98304)
        self.f.train_calls.clear(); self.f.generation_calls.clear()
        with self.assertRaisesRegex(b.EvidenceError, 'Unvisited branch output'):
            runner.execute()
        self.assertEqual(self.f.train_calls, [])
        self.assertEqual(self.f.generation_calls, [])

    def test_managed_output_from_different_evidence_is_rejected_early(self):
        runner = self.f.branch('S128'); runner.execute()
        runner.evidence_hash = 'a'*64
        self.f.train_calls.clear(); self.f.generation_calls.clear()
        with self.assertRaisesRegex(b.EvidenceError, 'Stale or mismatched managed stage plan'):
            runner.execute()
        self.assertEqual(self.f.train_calls, [])

    def test_barrier_rejects_stale_decision_execution_and_mutable_snapshot(self):
        path = self.f.evidence()
        receipt = self.f.run/'evidence/decision_execution.json'
        row = b.read(receipt); row['grades_sha256'] = '0'*64; write(receipt, row)
        ready = b.read(path); ready['artifacts']['decision_execution']['sha256'] = b.sha(receipt); write(path, ready)
        with self.assertRaisesRegex(b.EvidenceError, 'Stale decision execution'):
            self.r.barrier(path)
        path = self.f.evidence()
        current = write(self.f.run/'scores/current.json', [])
        ready = b.read(path); ready['artifacts']['initial_scores'] = dict(path=str(current), sha256=b.sha(current)); write(path, ready)
        with self.assertRaisesRegex(b.EvidenceError, 'immutable phase snapshot'):
            self.r.barrier(path)

    def test_barrier_does_not_parse_review_contents(self):
        path = self.f.evidence()
        forbidden = {str(self.f.run/f'evidence/{role}.json') for role in
                     ('review_packets', 'review_mapping', 'review_grades', 'review_receipt')}
        original_read = b.read
        def guarded_read(path):
            self.assertNotIn(str(path), forbidden)
            return original_read(path)
        with mock.patch.object(b, 'read', side_effect=guarded_read), mock.patch.object(self.r, 'validate_initial'):
            self.r.barrier(path)

    def test_full_initial_metadata_barrier_and_source_hash_binding(self):
        rows = self.f.initial()
        path = self.f.evidence(rows=rows)
        self.r.barrier(path)
        self.assertEqual(len(rows), 1324)
        self.assertEqual(self.r.floor, {j['id']: 32768 for j in self.f.main12})
        self.assertEqual(len(self.r.initial_sources), 3)
        rowpath = Path(rows[0]['file'])
        row = b.read(rowpath); row['raw_text'] = 'drift'; write(rowpath, row)
        with self.assertRaisesRegex(b.EvidenceError, 'score snapshot does not match'):
            self.r.barrier(path)

    def test_initial_length_hit_without_extensions_refuses_gate(self):
        self.f.hits[('Base', 32768)] = {'q00'}
        rows = self.f.initial()
        with self.assertRaises(b.EvidenceError):
            self.r.barrier(self.f.evidence(rows=rows))

    def test_initial_extension_replay_binds_superseded_source_hashes(self):
        self.f.hits[('Base', 32768)] = {'q07'}
        self.f.hits[('DX512', 32768)] = {'q09'}
        original = self.f.initial()
        active = [self.f.main12[7], self.f.main12[9]]
        path = write(self.f.run/'extensions/jobs-main-common-81920.json', active)
        extended = []
        for arm in b.INITIAL_ARMS:
            out = self.f.make_output(arm, 'main', path, cap=81920, context=98304, suffix='-common')
            for job in active:
                file = out/f"{job['id']}-0.json"
                extended.append(dict(arm=arm, kind='main', training_seed=2026093001, id=job['id'],
                                     cap=81920, file=str(file), file_sha256=b.sha(file), finish_reason='stop'))
        final = [row for row in original if row['kind'] != 'main' or row['id'] not in {'q07','q09'}] + extended
        self.r.validate_initial(final, original + extended)
        self.assertEqual(self.r.floor['q07'], 81920)
        self.assertEqual(self.r.floor['q00'], 32768)
        superseded = self.f.run/'outputs/Base-2026093001-main-32768/q07-0.json'
        row = b.read(superseded); row['raw_text'] = 'changed superseded source'; write(superseded, row)
        with self.assertRaisesRegex(b.EvidenceError, 'all-stage source hashes differ'):
            self.r.validate_initial(final, original + extended)

    def initial_censor_fixture(self, kind, group):
        jobs = b.read(self.f.run / ('jobs/main24.json' if kind == 'main' else 'jobs/retention.json'))
        job = jobs[12] if group == 'rep2' else jobs[0]
        self.f.hits[('Base', 32768)] = {job['id']}
        original = self.f.initial()
        arms = b.INITIAL_ARMS[:3] if group == 'rep2' else b.INITIAL_ARMS
        extended = []
        for cap, context in b.BOUNDS[1:]:
            self.f.hits[('Base', cap)] = {job['id']}
            path = write(self.f.run / f'extensions/jobs-{kind}-{group}-{cap}.json', [job])
            for arm in arms:
                out = self.f.make_output(arm, kind, path, cap=cap, context=context, suffix='-'+group)
                file = out / f"{job['id']}-0.json"
                extended.append(dict(arm=arm, kind=kind, training_seed=2026093001, id=job['id'],
                    cap=cap, file=str(file), file_sha256=b.sha(file), finish_reason=b.read(file)['finish_reason']))
        final = [r for r in original if r['kind'] != kind or r['id'] != job['id']]
        final += [r for r in extended if r['cap'] == 131072]
        receipt = write(self.f.run / f'extensions/censored-{kind}-{group}.json',
                        dict(ids=[job['id']], cap=131072, arms=list(arms)))
        return final, original + extended, receipt

    def test_completed_final_censored_replication_does_not_block_initial_gate(self):
        final, all_stages, _ = self.initial_censor_fixture('main', 'rep2')
        self.r.validate_initial(final, all_stages)
        self.assertEqual(len(final), 1324)
        self.assertTrue(all(cap == 32768 for cap in self.r.floor.values()))

    def test_final_censored_replication_requires_exact_censor_receipt(self):
        final, all_stages, receipt = self.initial_censor_fixture('main', 'rep2')
        row = b.read(receipt); row['ids'] = []; write(receipt, row)
        with self.assertRaisesRegex(b.EvidenceError, 'Missing final censor receipt'):
            self.r.validate_initial(final, all_stages)

    def test_final_censored_common_main_still_refuses_initial_gate(self):
        final, all_stages, _ = self.initial_censor_fixture('main', 'common')
        with self.assertRaisesRegex(b.EvidenceError, 'Initial gate comparison is censored'):
            self.r.validate_initial(final, all_stages)

    def test_final_censored_retention_still_refuses_initial_gate(self):
        final, all_stages, _ = self.initial_censor_fixture('retention', 'all')
        with self.assertRaisesRegex(b.EvidenceError, 'Initial gate comparison is censored'):
            self.r.validate_initial(final, all_stages)


if __name__ == '__main__':
    unittest.main()
