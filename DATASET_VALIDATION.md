# Dataset validation — follow-up audit, 2026-10-27

The previous blocked reports are retained unchanged. Current evidence is in
`reports/audit-20261027/`, with machine-readable source provenance in
`data/audit-20261027/source-manifest.json` (copied into the new real runs).

| Track | Verified evidence | Current status |
|---|---|---|
| CoreSNP cohort | All six compressed/decompressed SHA256 identities match prior evidence; gzip CRC rechecked; 3,024 unique FID/IID pairs, 404,388 loci, chromosomes 1–12; BED dimensions 305,717,331 = 3 + 404,388 × ceil(3024/4) | VERIFIED; cached files reused |
| Individual B001 VCF | Original source HEAD 2,187,654,873 bytes; original 339,302-byte TBI works; indexed chr01:1000000–1010000 gives 10,001 observed records, seven SNPs and 9,994 reference records | VERIFIED_REGION |
| Matching FASTA | Exact RAP-DB IRGSP-1.0 file on current official NARO host; publisher MD5 verified, local SHA256 recorded, all header contigs/lengths and all 10,001 observed REF bases checked with RiceFlow and independently BCFtools | VERIFIED_REGIONAL_BASES |

The cohort compressed SHA256 values remain:

- BED: `bc0d092504d2b349c1714710501531b3434fb5c602f30ebf2f0c16c1f3754382`
- BIM: `ccdcc75790bcaba1bdb4b13c9b133bfa28a2966bbcde159ee62ff187e3526ee9`
- FAM: `ded6261e398e73e311ad8613dffbea8acc1b1a68f3066a9e072150577687ec00`

The first 24 lexical FID/IID pairs are B001–B021, B023, B024 and B025. B022 is absent from the source;
the old prose “B001 through B024” was incorrect. Archived selected.samples files already contained the
correct identities. In chr1:1–1,000,000 inclusive, 969 loci are selected and 824 retained with sample/site
call-rate choices 0.8/0.9; all 24 samples remain. These were recomputed, not forced to expected values.

## Reference access diagnosis and identity

The legacy `rapdb.dna.affrc.go.jp` endpoint presents a chain signed by an untrusted Fortinet appliance
CA on the observed network path. Verified Python HTTPS and OpenSSL reject it. This does not establish
that the publisher's origin certificate itself is bad. The current official publisher hostname
`rapdb.dna.naro.go.jp` succeeds using the same default trust store and clock. Server Date agrees with
the execution clock; no clock-related failure was observed. No arbitrary CA was trusted, no TLS or
hostname check was disabled, and no system-wide trust setting or insecure HTTP fallback was used.
See `reports/audit-20261027/tls-diagnosis.json`.

- Assembly/release: **Os-Nipponbare-Reference-IRGSP-1.0**, the exact assembly/file named by the original [3kRG reference README](https://3kricegenome.s3.amazonaws.com/README-rice-reference-genomes-used.txt).
- Current authoritative [RAP-DB assembly page](https://rapdb.dna.naro.go.jp/download/irgsp1.html).
- [FASTA gzip](https://rapdb.dna.naro.go.jp/download/archive/irgsp1/IRGSP-1.0_genome.fasta.gz), retrieved 2026-10-27 with verified HTTPS.
- Compressed size: **121,184,922 bytes**; decompressed FASTA: **379,466,370 bytes**.
- [Publisher MD5](https://rapdb.dna.naro.go.jp/download/archive/irgsp1/IRGSP-1.0_genome.fasta.gz.md5): `5c5750e0d06b54b7360b35be73aef3de`.
- Compressed SHA256: `fc71a8c1798841dbc6655bbacdb745a0caf248dcfd57b59a35bc249fecc4145b`.
- FASTA SHA256: `c60dd24591bc151eb2c9253a4c8ffbef3f9e50a69e7e3ddb905209087f16467b`.

The exact publisher file, its checksum and the original project README establish release identity;
matching a single chromosome length alone was not accepted. All 12 VCF contig names/lengths match the
FASTA exactly, so the alias map is empty. Soft-masked lowercase bases are compared case-insensitively;
the FASTA and REF alleles are not rewritten or swapped. `bcftools norm -f ... -c e` independently
accepted all 10,001 selected records. Header compatibility and observed REF checks do not claim a
whole-genome validation of the multi-gigabyte VCF.

The published gzip is not remotely indexed at the tested `.fasta.fai` / `.fasta.gz.fai` sidecar URLs
(both returned 404), so a full bounded gzip retrieval was used after HEAD size discovery, then indexed
locally. A subsequent preflight reused both cohort and reference caches with a **1 MiB full-transfer
budget**, transferring only small metadata/index payloads, and rechecked all source hashes.

## VCF scope and quality fields

The deterministic region is chr01:1000000–1010000, one-based inclusive. It contains seven heterozygous
biallelic SNP records and 9,994 explicit reference records; no unsupported variants were observed there.
B001 is a single diploid sample. The header declares GT/DP/GQ/AD/PL, but actual formats include GT:DP
and GT:AD:DP:GQ:PL. All seven SNPs carry DP (25–39) and GQ (34–99); reference records lack GQ.
Reference records are retained separately and excluded from SNP QC denominators.

Default DP≥5, GQ disabled, sample call rate≥0.8 then site call rate≥0.9 retains all seven SNP calls.
The separate GQ40 policy masks chr01:1001391 (GQ34), retains the sample at 6/7 observed SNP sites, then
retains six sites. Source FILTER is preserved, including LowQual records that pass the configured
policy. Final completeness 6/6 reflects exclusion of the masked site, not improved biological accuracy.

## Retrieval budgets and usage context

Preflight defaults remain 500 MiB full payload bytes, 16 MiB regional payload bytes, 100 requests,
30-second socket timeouts and at most three GET attempts with bounded backoff. HEAD discovers full
sizes; unknown sizes are rejected. Ranged GET requires HTTP 206, exact Content-Range and matching
payload length. A server ignoring Range is rejected before body consumption. ETag is never SHA256.

The first new preflight transferred 121,526,242 full-payload bytes (mainly FASTA and the VCF index) and
423,473 range bytes, with zero cohort redownloads. Prior recorded data transfers plus this audit and
the cache-reuse check stay below 500 MiB full / 16 MiB regional limits. HTTP/TLS overhead and software
container/dependency transfers are outside genomic payload counters and are not mislabeled as data.
The complete 2.19 GB VCF was never downloaded; its full-file SHA256 is intentionally unavailable.

CoreSNP is already filtered and LD-pruned: this is downstream QC, not original discovery. BIM A1/A2
order does not establish REF/ALT; native cohort PLINK outputs remain reference-unvalidated. No cohort
VCF is exported and no DP/GQ is invented for PLINK. Both tracks remain separate.

Official dataset sources and usage statements remain:
[registry](https://registry.opendata.aws/3kricegenome/),
[download page](https://3kricegenome.s3.us-east-1.amazonaws.com/3kRG_download.html),
[IRIC AWS](https://iric.irri.org/resources/3krg-in-aws), and
[SNP-Seek datasets](https://iric.irri.org/resources/snp-seek-datasets).
The source BAM/VCF and SNP READMEs require the spirit of the Toronto Statement. RAP-DB remains the
reference publisher; no different assembly or additional accession was substituted.
