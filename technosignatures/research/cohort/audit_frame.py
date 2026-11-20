"""Validate frozen metadata-response hashes and summarize finite-frame coverage."""
import json, hashlib
from collections import Counter,defaultdict
from pathlib import Path
from urllib.parse import urlsplit
import numpy as np
from research.cohort.frame import HERE,write,digest


def main():
    selection=json.loads((HERE/'evidence/selection.json').read_text())
    frames=[]; all_hashes=True
    for year,expected in sorted(selection['input_frame_sha256'].items()):
        p=HERE/f'evidence/frames/{year}.json'; f=json.loads(p.read_text()); attempts=f['attempts']
        hashes=[hashlib.sha256(json.dumps(a['canonical_response'],sort_keys=True).encode()).hexdigest()==a['response_sha256'] for a in attempts if 'canonical_response' in a]
        valid=digest(p)==expected and all(hashes); all_hashes &= valid
        frames.append({'year':int(year),'selection_bound_file_hash_verified':digest(p)==expected,'canonical_response_hashes_verified':all(hashes),'indexed_rows':len(f['rows']),'queries':len(attempts),'saturated_parent_queries':sum(a.get('saturated',False) for a in attempts),'failed_queries':sum('canonical_response' not in a for a in attempts),'effective_http_query_count':sum(urlsplit(a.get('effective_url','')).scheme=='http' for a in attempts),'api_frame_complete':f['frame_complete_with_respect_to_unsaturated_api_queries']})
    weights=[s['sampling_weight'] for s in selection['selection']]
    rejections=selection['rejected_sequences']
    result={'selection_sha256':digest(HERE/'evidence/selection.json'),'all_frame_and_canonical_response_hashes_verified':all_hashes,'frames':frames,'eligible_cadence_product_proposals':len(selection['cadences']),'parent_cadence_product_proposals':len(selection['linkage_parent_cadences']),'linked_components':len(selection['linkage']['components']),'selected_components':len(selection['selection']),'eligible_proposal_count_by_selected_component':weights,'total_inverse_inclusion_weight':sum(weights),'largest_component_fraction_of_eligible_proposals':max(weights)/sum(weights),'weight_concentration_kish_diagnostic':sum(weights)**2/sum(w*w for w in weights),'weight_diagnostic_caution':'Describes concentration of the seven component weights only; not an inferred number of independent astronomical samples.','recorded_rejection_reason_counts':dict(Counter(r for x in rejections for r in x['reasons'])),'rejection_unit_caution':'Rows, duplicate products and six-scan sequences are different units; reasons overlap and these counts are not a mutually exclusive attrition denominator. Target-pattern windows rejected before geometry are not separately recorded by the frozen assembly.','metadata_transport_limit':'Some archived effective API URLs use HTTP after redirects. Canonical response hashes prove record integrity and repeatability, not end-to-end authenticated catalogue provenance. Source byte-range acquisition separately enforces HTTPS.','selection_coverage_limits':['API completeness is conditional on the fixed time/frequency/telescope/product queries, not independently verified sky or archive completeness.','The query uses product center frequencies, not an exhaustive overlap inventory of all possible spectral products.','Only declared six-scan alternating target patterns meeting beam-relative geometry enter the frame.','Dependency linkage is conservative but unidentified campaign/target aliases may remain.'],'main_60_component_gate_passed':False}
    write(HERE/'evidence/catalogue_coverage_audit.json',result)
    assert all_hashes
    print({k:result[k] for k in ['all_frame_and_canonical_response_hashes_verified','total_inverse_inclusion_weight','largest_component_fraction_of_eligible_proposals','weight_concentration_kish_diagnostic']})


if __name__ == "__main__": main()
