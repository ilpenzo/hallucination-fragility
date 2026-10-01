"""Which inputs the revision analyses read, with SHA-256 digests, so a reader can check that the reported numbers
come from the corrected files and the original raw responses. Works in both layouts; paths are root-relative."""
import glob, hashlib
from common import *
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def sha_dir(d, pattern):
    h = hashlib.sha256(); fs = sorted(glob.glob(os.path.join(d, pattern)))
    for f in fs: h.update(os.path.relpath(f, d).encode()); h.update(open(f, 'rb').read())
    return {'n_files': len(fs), 'sha256_of_names_and_contents': h.hexdigest()}
single = [('P1 scores after the extraction fix (input to adjudication, tolerance sweep, replication comparison)', FIXED),
          ('P1 scores with the seven AI-review corrections (source of Table 1 and of the P1 column of Table 6)', ADJUDICATED),
          ('P1 replication scores, same extraction rule', FIXED_REPL),
          ('Case-level P1 adjudication records (AI review)', os.path.join(OUT, 'p1_adjudication_records.json')),
          ('Verified feasibility labels (output of p2_feasibility.py; read by every P2 script)', os.path.join(OUT, 'p2_feasibility_classes.json')),
          ('Rubric labels for the 400 turn-15/turn-17 responses, core batch only', os.path.join(OUT, 'incompatibility_llm_labels_core_feb2026.json')),
          ('Cross-judge comparison table (Appendix A)', IRR_CSV)]
dirs = [('Raw P2 responses, core run (never modified)', RESULTS, os.path.join('*', 'P2_*.json')), ('Raw P1 responses, core run (never modified)', RESULTS, os.path.join('*', 'P1_*.json')),
        ('Raw P2 responses, replication run', RESULTS_REPL, os.path.join('*', 'P2_*.json')), ('Historical P2 scenarios (unchanged)', P2_SCEN, 'P2_*.json'),
        ('P3 judge outputs, core batch', JUDGED, '*.json'), ('P3 judge outputs, supplementary batch (February 2026)', JUDGED_SUPP, '*.json'),
        ('P3 judge outputs, contemporary batch: new scenarios', JUDGED_R2, '*.json'), ('P3 judge outputs, contemporary batch: comparison scenarios', JUDGED_R2_CTRL, '*.json')]
out = {'layout': LAYOUT, 'files': [{'role': r, 'path': rel(p), 'sha256': sha(p)} for r, p in single if os.path.exists(p)],
       'directories': [dict({'role': r, 'path': rel(d), 'pattern': pat}, **sha_dir(d, pat)) for r, d, pat in dirs if os.path.isdir(d)],
       'not_used_for_any_revised_P2_number': 'P2 fields of the scored_results files, p2_parser_analysis/, p2_rescore_results/ (originally submitted scoring; historical)'}
md = '| Role | Path | Files | SHA-256 (first 16) |\n|---|---|---|---|\n' + ''.join(f"| {x['role']} | `{x['path']}` | 1 | `{x['sha256'][:16]}` |\n" for x in out['files']) + ''.join(f"| {x['role']} | `{x['path']}/{x['pattern']}` | {x['n_files']} | `{x['sha256_of_names_and_contents'][:16]}` |\n" for x in out['directories'])
print(md); save('inputs_manifest', out, md)
