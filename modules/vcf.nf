process VCF_QC {
    cpus 1
    memory '2 GB'
    input:
    path vcf
    path fasta
    path fai
    val policy_json
    val sample
    val input_hashes
    val region
    val code_fingerprint
    output:
    path 'vcf', emit: result
    script:
    def cfg = groovy.json.JsonOutput.toJson([vcf:vcf.toString(), reference:'indexed.reference.fa', expected_sample:sample, execution_code_fingerprint:code_fingerprint, vcf_region:region, input_sha256:new groovy.json.JsonSlurper().parseText(input_hashes)])
    """
    cat > policy.json <<'POLICY'
    ${policy_json}
    POLICY
    cat > cfg.json <<'JSON'
    ${cfg}
    JSON
    bcftools view -Ov '${vcf}' -o checked.vcf
    bcftools stats checked.vcf > bcftools.stats.txt
    cp '${fasta}' indexed.reference.fa
    samtools faidx indexed.reference.fa
    riceflow vcf --config cfg.json --policy policy.json --out vcf
    cp bcftools.stats.txt vcf/
    bcftools --version > vcf/tool-versions.txt
    samtools --version >> vcf/tool-versions.txt
    """
}
