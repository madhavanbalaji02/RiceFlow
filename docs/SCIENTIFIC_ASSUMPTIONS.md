# Scientific scope and assumptions

Rice is modeled as diploid with 12 autosomes and no sex/mitochondrial chromosome codes in this release.
Unexpected contigs, ambiguous alleles, duplicate/conflicting positions, non-diploid calls, malformed
binary dimensions, and reference mismatches fail validation. Numeric source variant IDs need not be
unique across chromosomes. Contig names are never silently renamed to satisfy reference checks.

The CoreSNP source is already selected and LD-pruned. This demonstration examines missingness,
allele counts and descriptive heterozygosity on a deterministic small downstream subset. It cannot
assess original read depth, variant-calling sensitivity, population LD or genome-wide cohort quality.
The sample ordering is lexical FID then IID; interval endpoints are inclusive. Selection is reproducible,
not representative sampling and not evidence of a population-level biological finding.

Quality masking occurs first in the individual-VCF track, then sample assessment and exclusion, then
site metric recomputation. Reference records are counted but are outside biallelic SNP QC. Unsupported
alleles are explicit scope exclusions. Partial GTs count as uncalled and do not contribute half an
allele denominator. Absent records remain unknown. Individual accession observations are never joined
by substituting reference GTs and never called a jointly genotyped cohort.

Default analysis choices: sample call rate 0.8, site call rate 0.9, DP >=5, GQ disabled, missing enabled
quality not_assessed and masked, MAF >=0. The tiny fixture demo uses sample call rate 0.4 deliberately
to retain its sample with many constructed failures. No HWE threshold is used for this crop dataset.
Sensitivity grids are descriptive threshold comparisons on the same inputs; they do not optimize
accuracy or justify a chosen cutoff. All choices belong in the run manifest.

Imputation remains unimplemented and disabled. Future work requires compatible independent panels,
explicit panel/evaluation separation, reproducible held-out genotype masking, crop-appropriate models,
leakage checks and a baseline comparison before any accuracy claim. Pangenome construction and
haplotype expansion are outside this release.

## Follow-up audit clarification, 2026-10-27

RAP-DB's current NARO hostname provides the exact IRGSP-1.0 file identified by the original project
README. Its publisher MD5, local SHA256, all declared contig lengths and all observed regional REF
bases have now been validated. The reference is soft-masked; case is ignored only for base comparison.
No contig alias, allele swap or REF rewrite was applied. This is regional validation, not proof that
all records in the 2.19 GB VCF have correct reference alleles.

Reference-only records remain fully preserved in reference-records.vcf.gz, outside SNP DP/GQ filtering.
Unsupported records have their own indexed file. The source GT/quality/INFO/FILTER remain in those
scope outputs. SNP masking preserves OGT, QCR and source FILTER, and removes stale source allele/count
INFO tags including MLEAC/MLEAF; likelihood and depth fields remain original measurements.

The real default policy retains all seven observed SNPs in chr01:1000000–1010000. GQ is present on all
seven SNPs, so a separate GQ40 demonstration is interpretable on those seven observations. It does not
make GQ universally applicable: the 9,994 reference records have no GQ and remain scope exclusions.
The GQ40 threshold is a deliberately named analysis choice after inspecting availability, not an
optimized or biologically validated cutoff. It masks one GQ34 SNP, yields 6/7 completeness after masking,
and retains six sites after recomputation. Final 6/6 completeness uses a different site denominator.

Sensitivity comparisons now vary exactly one threshold at a time; other choices and the original
observed SNP denominator are recorded on each row. The DP30 sensitivity choice masks the DP25 call,
while the default DP5 rule masks none in this small interval. No accuracy or whole-genome quality
improvement follows from these descriptive results. A second accession was unnecessary for these gates.

The source VCF header reports upstream UnifiedGenotyper with diploid calls and EMIT_ALL_SITES output.
This explains the explicit reference records as source observations; the upstream discovery pipeline
is historical context and was not rerun or scientifically reproduced in this project.
