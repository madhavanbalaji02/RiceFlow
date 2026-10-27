from pathlib import Path
import json
import yaml
c = yaml.safe_load(Path('config/demo.yaml').read_text())
for k in ['cohort', 'vcf', 'reference']:
    c[k] = str(Path(c[k]).resolve())
Path('.tools/nf-config.json').write_text(json.dumps(c, indent=2) + '\n')
Path('.tools/policy.json').write_text(json.dumps(c['policy'], indent=2) + '\n')
