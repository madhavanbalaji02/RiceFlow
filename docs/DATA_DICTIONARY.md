# Metric definitions

| Field | Definition / denominator |
|---|---|
| complete | Both alleles observed in a diploid GT; phased and unphased treated equally |
| partial | Exactly one allele missing, e.g. 0/.; contributes no alleles or heterozygosity |
| missing | Both alleles absent; no inferred reference calls |
| sample call_rate | complete calls / observed selected biallelic SNP sites at that stage |
| site call_rate | complete calls / assessed retained samples at that stage |
| heterozygosity | heterozygous complete calls / all complete calls; descriptive, not PLINK's F statistic |
| allele1_count | BED BIM A1 copies, or VCF ALT copies, from complete diploid calls only |
| allele_number | Twice the number of complete calls |
| allele1_frequency | allele1_count / allele_number; null if no alleles observed |
| maf | min(frequency, 1-frequency); no default rare-variant filter |
| baseline (cohort) | Selected unfiltered samples and sites; no DP/GQ exists |
| original (VCF) | Observed SNP genotypes before quality masking |
| baseline (VCF) | SNP genotypes after quality masking, before sample exclusion |
| after_sample_sites | Site metrics recomputed after samples fail call-rate policy |
| final | Site-filtered retained sample matrix; sample metrics recomputed again |
| scope_exclusions | Reference-only ALT='.' or unsupported variant records; outside SNP denominator |
| quality_status | passed, failed (observed below cutoff), not_assessed (required value unavailable), or scope_exclusion |

Unavailable ratios are JSON null / Parquet null / empty TSV fields, never artificial zero.
SNPs with no complete alleles cannot pass a frequency/site assessment even if thresholds are zero.
An empty result is EMPTY, never SUCCESS. Empty tables carry an `empty` boolean column with zero rows;
the summary JSON supplies the empty list. Header and row-level quality availability are distinct.
Default GQ rule is disabled; missing enabled quality defaults to not_assessed with conservative masking.
Optional missing-quality policies `fail` and `error` must be explicitly selected. A quality assessment
can pass for an originally missing genotype; genotype completeness is counted separately.

Source FILTER is preserved exactly in the output VCF. It is not a second implicit QC threshold.
OGT and QCR preserve original calls and per-call decisions in masked/filtered VCFs. The audit table
also retains reference/unsupported records, DP, GQ, original FILTER and GT. Original VCF is an input
checksum artifact; masked output covers supported SNPs. Stale source AC/AN/AF/NS tags are removed
following masking. The frequency tables recompute counts from masked complete calls.

Cohort source IDs are mapped to `chrom:position:A1:A2`; VCF keys use `contig:position:REF:ALT`.
These track-specific keys must not be treated as equivalent reference-oriented alleles.
Intervals in config and the report are one-based inclusive. pysam fetch uses `[start-1,end)`.
BED genomic interval files (different from PLINK binary BED) use zero-based half-open coordinates.
The fixture retrieval test proves that both configured inclusive boundaries are retained.

PLINK comparison uses `--nonfounders` to match all-sample counts. BIM A1 maps to provisional ALT in
PLINK 2 BED imports, but that is a file convention rather than biological reference validation.
Missingness uses complete calls. BCFtools query preserves partial GTs, whereas RiceFlow intentionally
excludes both alleles from its complete-diploid AC/AN. BCFtools `stats` record/SNP scope counts are
compared independently; no claim is made that all tool summary denominators are interchangeable.
