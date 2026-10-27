process COHORT_QC {
    cpus 1
    memory '2 GB'
    input:
    path bed
    path bim
    path fam
    val policy_json
    val settings
    output:
    path 'cohort', emit: result
    script:
    def cfg = new groovy.json.JsonSlurper().parseText(settings)
    cfg.cohort = 'input'
    def encoded = groovy.json.JsonOutput.toJson(cfg)
    """
    ln -s '${bed}' input.bed
    ln -s '${bim}' input.bim
    ln -s '${fam}' input.fam
    cat > policy.json <<'POLICY'
    ${policy_json}
    POLICY
    cat > cfg.json <<'JSON'
    ${encoded}
    JSON
    riceflow cohort --config cfg.json --policy policy.json --out cohort
    plink2 --version > cohort/tool-versions.txt
    """
}
