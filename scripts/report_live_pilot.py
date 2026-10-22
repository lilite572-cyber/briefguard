#!/usr/bin/env python3
"""Export/recheck completed pilot evidence offline. Never reads keys or calls APIs."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from briefguard.pilot import human_labels, summarize
from briefguard.pilot_v2 import validate_preparation


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(directory):
    plan = read(directory / "cases.json")
    outcomes = read(directory / "outcomes.json")
    labels = human_labels(directory, plan)
    expected = {(c["case_id"], m) for c in plan["cases"] for m in ("uniform", "change", "adaptive")}
    require(len(outcomes) == len(expected) == 18, "Incomplete outcome inventory")
    require({(r['case_id'], r['method']) for r in outcomes} == expected, "Duplicate/missing outcomes")
    summary = read(directory / "summary.json")
    recomputed = summarize(plan, outcomes, labels)
    require(all(summary[k] == v for k, v in recomputed.items()), "Saved summary differs from outcomes")
    require(summary['human_labels_sha256'] == sha(directory / 'human_review.csv'), "Human labels changed")
    cost = Decimal(0)
    input_tokens = output_tokens = citations = aligned = 0
    outside = []
    for row in outcomes:
        result = row['result']
        require('error' not in row, "Unexpected operational failure")
        require(result['model_version'] == 'gpt-4.1-mini-2025-04-14', "Wrong model snapshot")
        indices = row['selected_indices']
        require(len(indices) == len(set(indices)) == 8, "Frame budget mismatch")
        usage = result['usage']
        input_tokens += usage['input_tokens']
        output_tokens += usage['output_tokens']
        cost += (Decimal(usage['input_tokens']) * Decimal('0.4') + Decimal(usage['output_tokens']) * Decimal('1.6')) / Decimal(1000000)
        label = labels[row['case_id']]
        for evidence in result['evidence']:
            citations += 1
            require(evidence['frame_index'] in indices, "Citation to an unsupplied frame")
            if label['label'] == 'fail':
                matches = label['start_frame'] <= evidence['frame_index'] < label['end_frame']
                aligned += matches
                if not matches:
                    outside.append({'case_id':row['case_id'], 'method':row['method'], **evidence})
    accounting = summary['api_accounting']
    require(cost == Decimal(str(accounting['known_usage_cost_estimate_usd'])), "Cost/usage mismatch")
    require(accounting['attempts'] == 18 and accounting['attempts_without_known_cost'] == 0, "Accounting incomplete")
    return {'outcomes':len(outcomes), 'input_tokens':input_tokens, 'output_tokens':output_tokens,
            'usage_cost_estimate_usd':float(cost), 'schema_valid_supplied_frame_citations':citations,
            'citations_inside_human_event_interval':aligned, 'citations_outside_human_event_interval':outside,
            'interpretation':'Post-hoc interval consistency check, not an independent human factuality review. Status recall does not validate the explanation.',
            'independent_natural_sources':len({c['source_id'] for c in plan['cases'] if c['origin']=='natural_source_injected'}),
            'groups':recomputed['groups']}


def export(source, destination):
    require(not destination.exists(), "Export destination already exists; preserve it")
    plan = validate_preparation(source)
    status = read(source / 'guarded_execution_status.json')
    require(status['status'] == 'completed', 'Run is not complete')
    identity = read(source / 'run_identity.json')
    require(identity['labels_sha256'] == sha(source / 'human_review.csv'), 'Run label identity mismatch')
    require(identity['source_review_sha256'] == sha(source / 'source_confirmation.json'), 'Run source identity mismatch')
    require(identity['plan_sha256'] == sha(source / 'plan.json'), 'Run plan identity mismatch')
    rows = [read(path) for path in sorted((source / 'outcomes').glob('*.json'))]
    jobs = {(r['case_id'], r['method']):r for r in plan['jobs']}
    for row in rows:
        require(row['run_identity'] == identity, 'Outcome run identity mismatch')
        require(row['selected_indices'] == jobs[row['case_id'],row['method']]['selected_indices'], 'Selection drift')
    destination.mkdir(parents=True)
    public_rows = []
    for row in rows:
        clean = {k:row[k] for k in ['case_id','method','selected_indices','verification_wall_seconds']}
        clean['result'] = {k:row['result'][k] for k in ['status','evidence','model_version','usage','estimated_api_cost_usd']}
        if 'error' in row:
            clean['error'] = row['error']
        public_rows.append(clean)
    public_cases = {'cases':[{k:c[k] for k in ['case_id','source_id','origin','durations']} for c in plan['cases']]}
    for name, data in [('cases.json',public_cases), ('outcomes.json',public_rows),
                       ('summary.json',read(source/'summary.json')), ('execution_status.json',status),
                       ('input_freeze.json',read(source/'input_freeze.json')), ('run_identity.json',identity)]:
        (destination/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    (destination/'human_review.csv').write_bytes((source/'human_review.csv').read_bytes())
    evidence = metrics(destination)
    (destination/'offline_verification.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    manifest = {f.name:sha(f) for f in sorted(destination.iterdir()) if f.is_file()}
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return evidence


def verify(directory):
    for name, expected in read(directory/'manifest.json').items():
        require(Path(name).name == name, 'Manifest path must be a filename')
        require(sha(directory/name) == expected, 'Export file hash mismatch: '+name)
    evidence = metrics(directory)
    require(evidence == read(directory/'offline_verification.json'), 'Verification drift')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--verify',type=Path)
    args = parser.parse_args()
    if args.verify and not (args.source or args.out):
        result = verify(args.verify)
    elif args.source and args.out and not args.verify:
        result = export(args.source,args.out)
    else:
        parser.error('Use --verify DIRECTORY or --source PRIVATE_PACKET --out NEW_DIRECTORY')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
