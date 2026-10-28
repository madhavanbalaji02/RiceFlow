# Tool and source documentation review

Reviewed 2026-10-27. Current documentation was consulted before selecting flags; the project pins
older stable tool versions and tests the chosen command lines, rather than claiming “latest”.

- PLINK 2 input/chromosome semantics: https://www.cog-genomics.org/plink/2.0/input
  `--rice` is a haploid preset; this project explicitly uses 12 diploid autosomes and no human sex codes.
- PLINK statistics: https://www.cog-genomics.org/plink/2.0/basic_stats
  Native BED subsetting, `--missing`, `--freq counts`, and `--nonfounders` are tested against fixtures.
- Nextflow installation: https://docs.seqera.io/nextflow/install
  Java 17 is supported; tested controller 25.10.2 with Java 17.0.20.
- BCFtools manual: https://www.htslib.org/doc/bcftools.html
  Current manual differs from pinned 1.21; actual tested view/query/stats flags are stable.
- SAMtools faidx: https://www.htslib.org/doc/samtools-faidx.html
  Indexing uses a writable reference copy, never a staged input symlink.
- nf-test: https://www.nf-test.com/docs/getting-started/
  Pipeline integration assertions run through 0.9.3.
- Nextflow AWS Batch: https://docs.seqera.io/nextflow/reference/executor/aws-batch
- AWS Batch limits: https://docs.aws.amazon.com/batch/latest/userguide/managed_compute_environments.html
- Terraform Batch schema: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/batch_compute_environment
- IAM execution roles: https://docs.aws.amazon.com/batch/latest/userguide/execution-IAM-role.html

Provider 6.19.0 schemas were validated by Terraform 1.13.4 locally. The subsequently authorized Ohio
deployment executed both real tracks, verified artifacts and stopped compute. Observed IAM fixes,
runtime, cleanup and source identities are recorded in reports/aws-demo-20261027-summary.json.
Final invoice reconciliation and cloud restore/resume remain unverified; documentation alone does
not establish them. The cloud controller used distribution Java 17.0.21, recorded separately.
