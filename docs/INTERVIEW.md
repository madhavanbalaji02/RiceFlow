# Explaining the design in an interview

“I built a CPU-only rice QC workflow to demonstrate reproducible bioinformatics engineering. I kept
an already filtered PLINK cohort separate from accession-level VCF quality processing because these
inputs support different scientific questions. The workflow does not invent depth values for PLINK
or invent reference calls at absent VCF positions.

“I wrote explicit genotype and denominator rules, checked them on tiny hand-calculated fixtures,
and compared selected results independently with PLINK and BCFtools. Sample removal happens before
site statistics are recomputed. Partial calls, empty outputs and missing per-record fields have
explicit behavior. A declared GQ header never implies GQ exists on every record.

“Nextflow supplies scheduling and resumability; the Python launcher supplies durable final status
and checksums after Nextflow exits. I demonstrated failure followed by cached resume and confirmed
that a biological-policy change invalidates results. Scientific success requires validated artifacts
and a success marker, not an attractive HTML report.

“I verified the complete public CoreSNP files and ran a deterministic local subset. I retrieved small
B001 regions without downloading its multi-gigabyte VCF. The legacy reference hostname failed TLS verification, so the original report was correctly blocked.
In the follow-up audit I resolved the current official NARO hostname with normal verification,
checked its publisher checksum and all observed REF bases, and ran both real-data tracks. After
explicit cost authorization, I ran the same two tracks on AWS Batch, verified their equivalence
and confirmed controller shutdown and zero workers. I kept delayed billing and untested cloud
restore/resume behavior explicit.”

Tradeoffs to discuss: stable locus IDs versus source IDs; complete-call allele counting versus
partial-call conventions; native CPU adapters versus standalone container binaries; conservative
policy cache dependencies; deterministic selection versus representative sampling; retained work/cache
versus storage cost; alerts versus enforcement; local evidence versus independently verified cloud execution.
