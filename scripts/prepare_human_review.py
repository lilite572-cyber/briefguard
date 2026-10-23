"""Build a dev-only, method-blinded human label audit; never fills human labels."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from briefguard.data import iter_clips, MOTIONS, VIOLATION_TYPES
from PIL import Image


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def select_cases(rows):
    """One per type × severity × motion; deterministic source/duration balancing."""
    strata = defaultdict(list)
    for row in rows:
        a = row["annotation"]
        strata[(a["violation_type"] or "clean", a["severity"], a["motion"])].append(row)
    sources, durations, selected = Counter(), Counter(), []
    for stratum, candidates in sorted(strata.items()):
        row = min(candidates, key=lambda r: (sources[r["source_id"]], durations[r["annotation"]["duration_frames"]],
                    hashlib.sha256(("human-audit-v1:" + r["clip_id"]).encode()).hexdigest()))
        selected.append(row)
        sources[row["source_id"]] += 1
        durations[row["annotation"]["duration_frames"]] += 1
    return sorted(selected, key=lambda r: digest(["presentation-v1", r["clip_id"]]))


def prepare(run, out):
    run, out = Path(run), Path(out)
    metadata = json.loads((run / "metadata.json").read_text())
    if metadata.get("complete") is not True or metadata["identity"]["split"] != "dev":
        raise ValueError("Human audit uses a completed development run only")
    manifest = run / "manifest.jsonl.gz"
    rows = [json.loads(line) for line in gzip.open(manifest, "rt") if line.strip()]
    if any(r["split"] != "dev" for r in rows) or len({r["clip_id"] for r in rows}) != len(rows):
        raise ValueError("Invalid development manifest")
    config = metadata["identity"]["config"]
    sources = metadata["identity"]["source_ids"]
    if len(sources) != len(set(sources)) or any(type(i) is not int or i < 0 for i in sources):
        raise ValueError("Invalid source inventory")
    variants = [("clean", 0)] + [(kind, d) for kind in VIOLATION_TYPES for d in config["durations"]]
    expected = {f"s{source:06d}-{motion}-{kind}-{duration}": source for source in sources for motion in MOTIONS for kind, duration in variants}
    if {r["clip_id"] for r in rows} != set(expected) or any(r["source_id"] != expected[r["clip_id"]] for r in rows):
        raise ValueError("Incomplete or mismatched development source/clip inventory")
    chosen = select_cases(rows)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Output must be empty; do not overwrite a review package")
    reviewer = out / "reviewer"
    (reviewer / "assets").mkdir(parents=True)
    public, keys = [], []
    config = metadata["identity"]["config"]
    wanted = {r["clip_id"]: r for r in chosen}
    clips = {}
    for source in sorted({r["source_id"] for r in chosen}):
        for clip in iter_clips(source, config):
            if clip.clip_id not in wanted:
                continue
            row = wanted[clip.clip_id]
            if hashlib.sha256(clip.frames.tobytes()).hexdigest() != row["pixels_sha256"] or clip.annotation != row["annotation"]:
                raise ValueError("Generated pixels/annotations differ from saved evidence")
            if digest(clip.brief) != row["brief_sha256"]:
                raise ValueError("Generated public brief differs from saved evidence")
            case_id = "case-" + digest(["blind-v1", clip.clip_id])[:12]
            n, h, w = clip.frames.shape[:3]
            sheet = Image.new("RGB", (12 * w, ((n + 11) // 12) * h))
            for i, frame in enumerate(clip.frames):
                sheet.paste(Image.fromarray(frame), (i % 12 * w, i // 12 * h))
            asset = "assets/" + case_id + ".png"
            sheet.save(reviewer / asset)
            clips[clip.clip_id] = {"case_id": case_id, "brief": clip.brief, "frames": n,
                "width": w, "height": h, "fps": clip.brief["fps"], "columns": 12, "asset": asset,
                "asset_sha256": hashlib.sha256((reviewer / asset).read_bytes()).hexdigest()}
    for row in chosen:
        case = clips[row["clip_id"]]
        public.append(case)
        keys.append({"case_id": case["case_id"], "clip_id": row["clip_id"], "source_id": row["source_id"],
                     "annotation": row["annotation"], "pixels_sha256": row["pixels_sha256"]})
    payload = {"schema_version": "human-audit-v1", "cases": public}
    payload["dataset_id"] = digest(payload)
    (reviewer / "data.js").write_text("window.REVIEW_DATA = " + json.dumps(payload, separators=(",", ":")) + ";\n")
    (reviewer / "index.html").write_text(HTML)
    blank = {"schema_version": "human-labels-v1", "dataset_id": payload["dataset_id"],
             "reviewer_id": "", "reviewer_role": "human", "human_attestation": False,
             "labels": [{"case_id": c["case_id"], "decision": "", "violation_type": None,
                         "start_frame": None, "end_frame": None, "notes": ""} for c in public]}
    (reviewer / "blank_labels.json").write_text(json.dumps(blank, indent=2) + "\n")
    key = {"schema_version": "human-audit-key-v1", "dataset_id": payload["dataset_id"],
           "split": "dev", "run_id": metadata["run_id"], "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
           "sampling": "one per type/severity/motion; prefer unused sources and underrepresented durations; hash ties",
           "human_status": "pending", "public_payload": payload, "cases": keys}
    (out / "evaluator_key.json").write_text(json.dumps(key, indent=2) + "\n")
    return {"dataset_id": payload["dataset_id"], "cases": len(public), "source_groups": len({r["source_id"] for r in chosen}),
            "human_labels": "pending", "reviewer_directory": str(reviewer)}


HTML = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BriefGuard — human review</title><style>body{font:16px system-ui;max-width:1000px;margin:30px auto;padding:0 16px;background:#fafaf8;color:#18202b}button,input,select,textarea{font:inherit;padding:8px;margin:4px}canvas{width:min(768px,100%);image-rendering:pixelated;background:#222}textarea{width:90%;height:55px}#frame{width:75%}.warn{color:#9c3500}pre{white-space:pre-wrap}label{display:inline-block}button{cursor:pointer}fieldset{margin:14px 0}#error{color:#a00}</style>
<h1>BriefGuard human label audit</h1><p>Review all frames against the brief. Method answers and generator labels are hidden. This is a synthetic development-set audit, not an independent test. Do not open the evaluator key or the research replay until you export your labels.</p>
<p class="warn">No labels are saved automatically. Export a draft before closing and import it to resume. Use an alias; no personal details are needed.</p>
<label>Reviewer alias <input id="reviewer" placeholder="e.g. reviewer-1"></label><label><input id="attest" type="checkbox">I personally inspected these clips; these are human judgments.</label>
<p><button id="previous">Previous case</button><select id="case"></select><button id="next">Next case</button><span id="progress"></span></p>
<canvas id="view" width="128" height="72" aria-label="Exact video frame"></canvas><p><button id="back">−1 frame</button><button id="play">Play</button><button id="forward">+1 frame</button><span id="position"></span></p>
<input type="range" id="frame" min="0" max="95" value="0" aria-label="Frame timeline"><p id="pixel">Click a pixel to inspect RGB. Playback timing is approximate; the integer frame index is authoritative.</p>
<details open><summary>Public brief and target references</summary><ul id="requirements"></ul><pre id="reference"></pre></details>
<fieldset><legend>Your observation</legend><label>Decision <select id="decision"><option value="">Unreviewed</option><option value="violation">Violation</option><option value="compliant">Compliant</option><option value="unknown">Impossible to determine</option></select></label>
<label>Type <select id="kind"><option value="">—</option><option>missing_product</option><option>wrong_color</option><option>label_corruption</option><option>forbidden_patch</option></select></label><br>
<label>First violating frame <input id="start" type="number" min="0" max="95"></label><label>First compliant frame after event (exclusive end) <input id="end" type="number" min="1" max="96"></label>
<p>For a violation, record [start,end): frame end is excluded. For compliant/unknown, leave type and interval blank. Use unknown when you cannot judge; explain why.</p><textarea id="notes" placeholder="What did you observe? Explain uncertainty or ambiguity."></textarea></fieldset>
<button id="draft">Save draft JSON</button><label>Resume draft <input id="import" type="file" accept="application/json,.json"></label><button id="export">Export completed human labels JSON</button><p id="error" role="alert"></p><script src="data.js"></script><script>
'use strict';const D=window.REVIEW_DATA,$=id=>document.getElementById(id),ctx=$('view').getContext('2d');let current=0,frame=0,timer=null,img=null;
const labels=D.cases.map(c=>({case_id:c.case_id,decision:'',violation_type:null,start_frame:null,end_frame:null,notes:''}));
D.cases.forEach((c,i)=>{let o=document.createElement('option');o.value=i;o.textContent=(i+1)+' · '+c.case_id;$('case').appendChild(o)});
function save(){let r=labels[current];r.decision=$('decision').value;r.violation_type=$('kind').value||null;r.start_frame=$('start').value===''?null:Number($('start').value);r.end_frame=$('end').value===''?null:Number($('end').value);r.notes=$('notes').value; $('progress').textContent=labels.filter(r=>r.decision).length+'/'+labels.length+' reviewed'}
function draw(){let c=D.cases[current];if(img&&img.complete&&img.naturalWidth)ctx.drawImage(img,frame%c.columns*c.width,Math.floor(frame/c.columns)*c.height,c.width,c.height,0,0,c.width,c.height);$('frame').value=frame;$('position').textContent='Frame '+frame+' / '+(c.frames-1)+' · '+(frame/c.fps).toFixed(3)+' s'}
function stop(){clearInterval(timer);timer=null;$('play').textContent='Play'}
function show(i){stop();save();current=i;frame=0;let c=D.cases[i],r=labels[i];$('case').value=i;$('view').width=c.width;$('view').height=c.height;$('frame').max=c.frames-1;img=new Image();img.onload=draw;img.onerror=()=>{$('error').textContent='Could not load frame asset; do not review this case.'};img.src=c.asset;for(let pair of [['decision','decision'],['kind','violation_type'],['start','start_frame'],['end','end_frame'],['notes','notes']])$(pair[0]).value=r[pair[1]]??'';$('requirements').replaceChildren();c.brief.requirements.forEach(t=>{let li=document.createElement('li');li.textContent=t;$('requirements').appendChild(li)});let b=c.brief;$('reference').textContent='Target RGB: '+b.target_rgb+'; allowed lighting jitter ±'+b.benign_channel_jitter_max+'\nForbidden RGB: '+b.forbidden_rgb+'\nROIs [left,top,right,bottom], normalized:\n'+JSON.stringify({product:b.product_roi,color:b.color_roi,label:b.label_roi,forbidden:b.forbidden_roi},null,2)+'\nExpected NOVA bitmap (1 = light cell):\n'+b.label_bitmap.map(r=>r.join(' ')).join('\n');draw()}
$('case').onchange=()=>show(Number($('case').value));$('previous').onclick=()=>show((current+D.cases.length-1)%D.cases.length);$('next').onclick=()=>show((current+1)%D.cases.length);$('frame').oninput=()=>{stop();frame=Number($('frame').value);draw()};$('back').onclick=()=>{stop();frame=Math.max(0,frame-1);draw()};$('forward').onclick=()=>{stop();frame=Math.min(D.cases[current].frames-1,frame+1);draw()};$('play').onclick=()=>{if(timer){stop();return}$('play').textContent='Pause';timer=setInterval(()=>{frame=(frame+1)%D.cases[current].frames;draw()},1000/D.cases[current].fps)};
['decision','kind','start','end','notes'].forEach(id=>$(id).onchange=save);
$('view').onclick=e=>{try{let c=D.cases[current],r=$('view').getBoundingClientRect(),x=Math.min(c.width-1,Math.floor((e.clientX-r.left)*c.width/r.width)),y=Math.min(c.height-1,Math.floor((e.clientY-r.top)*c.height/r.height)),p=ctx.getImageData(x,y,1,1).data;$('pixel').textContent='Frame '+frame+', pixel ('+x+','+y+'): RGB '+[p[0],p[1],p[2]].join(', ')}catch(e){$('pixel').textContent='Pixel inspection needs localhost serving; frame viewing still works.'}};
function download(complete){save();let out={schema_version:'human-labels-v1',dataset_id:D.dataset_id,reviewer_id:$('reviewer').value.trim(),reviewer_role:'human',human_attestation:complete&&$('attest').checked,labels};if(complete&&(!out.reviewer_id||!out.human_attestation||labels.some(r=>!r.decision))){$('error').textContent='Enter reviewer alias, confirm human review and label every case before completed export.';return}let url=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)+'\n'],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=complete?'human_labels.json':'human_labels_draft.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('error').textContent=complete?'Exported. The Python scorer performs full interval/schema validation.':'Draft saved. Import this JSON to resume.'}
$('export').onclick=()=>download(true);$('draft').onclick=()=>download(false);
$('import').onchange=async()=>{try{let file=$('import').files[0];if(!file)return;let s=JSON.parse(await file.text());if(s.schema_version!=='human-labels-v1'||s.dataset_id!==D.dataset_id||!Array.isArray(s.labels)||s.labels.length!==labels.length)throw Error('Wrong package or incomplete label inventory');let map=new Map(s.labels.map(r=>[r.case_id,r]));if(map.size!==labels.length||D.cases.some(c=>!map.has(c.case_id)))throw Error('Duplicate or unknown case IDs');let recovered=D.cases.map(c=>{let r=map.get(c.case_id);if(!['','violation','compliant','unknown'].includes(r.decision)||typeof r.notes!=='string'||(r.violation_type!==null&&!['missing_product','wrong_color','label_corruption','forbidden_patch'].includes(r.violation_type))||[r.start_frame,r.end_frame].some(v=>v!==null&&(!Number.isInteger(v)||v<0||v>c.frames)))throw Error('Invalid draft field');return {case_id:c.case_id,decision:r.decision,violation_type:r.violation_type,start_frame:r.start_frame,end_frame:r.end_frame,notes:r.notes}});stop();labels.splice(0,labels.length,...recovered);$('decision').value=labels[current].decision;$('kind').value=labels[current].violation_type??'';$('start').value=labels[current].start_frame??'';$('end').value=labels[current].end_frame??'';$('notes').value=labels[current].notes;$('reviewer').value=typeof s.reviewer_id==='string'?s.reviewer_id:'';$('attest').checked=false;show(0);$('error').textContent='Draft restored. Confirm human review again before completed export.'}catch(e){$('error').textContent='Import rejected: '+e.message}};show(0);
</script></html>'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, default=ROOT / "results/dev")
    p.add_argument("--out", type=Path, default=ROOT / "human_review")
    args = p.parse_args()
    print(json.dumps(prepare(args.run, args.out), indent=2))

if __name__ == "__main__":
    main()
