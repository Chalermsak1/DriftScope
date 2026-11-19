"""Execute observational access validation and legacy-pipeline loss audits.

Run from project root: .venv/bin/python -m research.pilot.run
All output stays in research/pilot; original files/recorded results are checked.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
import time

import pipeline as legacy
import numpy as np
import matplotlib.pyplot as plt

from .observations import HERE, ROOT, digest, inspect_cadence, load_release
from .accounting import traced_search, survival_record, survival_summary, matching_rows


def write(path, value):
    legacy.write_json(path,value)


def preserved_original():
    manifest = json.loads((ROOT/"PROJECT_MANIFEST.json").read_text())
    changed = [name for name, entry in manifest.items() if not (ROOT/name).exists() or digest(ROOT/name) != entry["sha256"]]
    if changed:
        raise AssertionError(f"Original experiment changed: {changed}")
    plan_manifest=json.loads((ROOT/"research/planning/manifest.json").read_text())
    changed_plan=[name for name,entry in plan_manifest.items() if not (ROOT/name).exists() or digest(ROOT/name)!=entry["sha256"]]
    if changed_plan:raise AssertionError(f"Approved research plan changed: {changed_plan}")
    return {"original_manifest_files_verified":len(manifest),"approved_plan_manifest_files_verified":len(plan_manifest),"changed":changed,"changed_plan_files":changed_plan,"all_preserved":True}


def native_plot(output, key, powers, frequencies, meta):
    fig,axes=plt.subplots(6,1,figsize=(11,12),layout="constrained",sharex=True)
    lo,hi=np.percentile(powers,[1,99.5])
    df=(frequencies[-1]-frequencies[0])/(len(frequencies)-1)
    for ax, data, scan in zip(axes,powers,meta["scans"]):
        dt=scan["integration_s"]
        extent=[-df/2000,(frequencies[-1]-frequencies[0])/1000+df/2000,-dt/2,(data.shape[0]-.5)*dt]
        im=ax.imshow(data,origin="lower",aspect="auto",extent=extent,cmap="magma",vmin=lo,vmax=hi,interpolation="nearest")
        ax.set_ylabel("Scan time [s]")
        ax.set_title(f"{scan['role']} | {scan['source_name']} | cadence start +{scan['elapsed_start_s']:.1f} s",fontsize=10)
    axes[-1].set_xlabel(f"Frequency offset [kHz] from reconstructed {frequencies[0]/1e6:.9f} MHz")
    fig.colorbar(im,ax=axes,label="Recorded power [arbitrary units]",shrink=.8)
    fig.suptitle(f"{key} | Real released six-scan cutout | shared intensity scale",fontsize=13)
    fig.savefig(output/f"{key}_observational_cadence.png",dpi=130)
    plt.close(fig)


def observational_access(output):
    started=time.perf_counter()
    release,spec=load_release()
    all_meta={}
    catalogue=[]
    selected=None
    for key in sorted(release):
        meta,data,frequencies,offsets=inspect_cadence(key,release[key])
        all_meta[key]=meta
        if not meta["passes_structural_cadence_checks"]:
            raise AssertionError(f"Invalid released cadence {key}: {meta['checks']}")
        # Preserve the released float32 power exactly; safe non-object format.
        np.savez_compressed(output/f"{key}_observation.npz",power_ascending=data.astype(np.float32),frequency_hz=frequencies,scan_start_elapsed_s=offsets,integration_s=np.array([s["integration_s"] for s in meta["scans"]]))
        signature=tuple((s["source_name"],s["start_mjd"]) for s in meta["scans"])
        catalogue.append({"id":key,"target":meta["scans"][0]["source_name"],"first_mjd":meta["scans"][0]["start_mjd"],"utc_day_proxy":int(meta["scans"][0]["start_mjd"]),"signature":signature})
        if key=="mlc1":
            selected=(data,frequencies,offsets,meta)
            native_plot(output,key,data,frequencies,meta)
    signatures={c["signature"] for c in catalogue}
    duplicate_groups=[]
    for sig in sorted(signatures):
        members=[c["id"] for c in catalogue if c["signature"]==sig]
        if len(members)>1: duplicate_groups.append(members)
    # Explicit conservative grouping proxy, not a claim of telescope-log sessions.
    parent=list(range(len(catalogue)))
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]; i=parent[i]
        return i
    for i,a in enumerate(catalogue):
        for j,b in enumerate(catalogue[:i]):
            if a["target"]==b["target"] or a["utc_day_proxy"]==b["utc_day_proxy"] or a["signature"]==b["signature"]:
                parent[find(i)]=find(j)
    groups={}
    for i,c in enumerate(catalogue):groups.setdefault(str(find(i)),[]).append(c["id"])
    summary={
        "source":spec,"released_cutouts":len(release),"scans_with_headers":sum(len(m["scans"]) for m in all_meta.values()),
        "all_structural_cadence_checks_passed":True,"distinct_scan_sequence_count":len(signatures),
        "same_scan_sequence_different_cutout_groups":duplicate_groups,
        "conservative_target_or_utc_day_proxy_groups":list(groups.values()),
        "session_definition_limit":"UTC integer MJD day is only a conservative grouping proxy; telescope-session logs were not acquired",
        "access_scope":"all six released scan records and frequency cutouts accessible; full original bandwidth/integration counts not independently verified",
        "representative_cohort_gate_passed":False,
        "cohort_gate_reason":"candidate-selected release; shared acquisition sequences; no representative multi-session cohort",
        "metadata_and_export_elapsed_s":time.perf_counter()-started,
    }
    write(output/"observational_manifest.json",all_meta)
    write(output/"access_summary.json",summary)
    return summary,selected


def search_with_profile(data, frequencies, times, detector, label, profiles):
    start=time.perf_counter()
    search, trace, c=traced_search(data,frequencies,times,detector)
    profiles.append({"label":label,"wall_s":time.perf_counter()-start,"shape":list(data.shape),"searched_tracks":c["legacy_searched_track_trials"]})
    return search,trace,c


def native_and_cadence_injection(output, selected, config, detector, profiles):
    data,frequencies,offsets,meta=selected
    cfg=config["real_cadence_injection"]
    df=legacy.channel_spacing(frequencies)
    channel=cfg["global_start_channel"]
    amplitude=cfg["peak_amplitude_in_background_sigma"]*float(np.median([legacy.robust_sigma(data[i]) for i in (0,2,4)]))
    sigma=cfg["fwhm_channels"]*df/np.sqrt(8*np.log(2))
    native=[]; survivals=[]; after=data.copy(); deltas=np.zeros_like(data)
    global_f0=float(frequencies[0]+channel*df)
    for i,scan in enumerate(meta["scans"]):
        times=np.arange(data.shape[1])*scan["integration_s"]
        before_search,before_trace,c=search_with_profile(data[i],frequencies,times,detector,f"native_{i}",profiles)
        write(output/f"native_scan_{i}_catalogue.json",before_trace)
        write(output/f"native_scan_{i}_coverage.json",c)
        native.append({"scan_index":i,"role":scan["role"],"source_name":scan["source_name"],"coverage":{k:v for k,v in c.items() if k!='per_drift'},"catalogue":before_trace["summary"],"maximum_score":float(before_search["score_map"].max()),"score_map_sha256":hashlib.sha256(before_search["score_map"].tobytes()).hexdigest()})
        print(f"Native {i+1}/6: {before_trace['summary']['uncapped_nms_candidates']} uncapped candidates",flush=True)
        if scan["role"]=="ON":
            global_times=offsets[i]+times
            centers=(channel*df)+cfg["global_drift_hz_per_s"]*global_times
            relative_frequency=np.arange(data.shape[-1])*df
            delta=amplitude*np.exp(-.5*((relative_frequency[None,:]-centers[:,None])/sigma)**2)
            deltas[i]=delta;after[i]=data[i]+delta
            after_search,after_trace,_=search_with_profile(after[i],frequencies,times,detector,f"cadence_injected_{i}",profiles)
            truth={"start_channel_ascending":float(channel+cfg["global_drift_hz_per_s"]*offsets[i]/df),"start_frequency_hz":float(global_f0+cfg["global_drift_hz_per_s"]*offsets[i]),"drift_hz_per_s":cfg["global_drift_hz_per_s"],"global_start_frequency_hz":global_f0,"global_elapsed_scan_start_s":float(offsets[i]),"fwhm_hz":cfg["fwhm_channels"]*df,"peak_amplitude_power":amplitude}
            record=survival_record(f"mlc1_one_global_track_scan_{i}",truth,frequencies,times,detector,before_search,after_search,after_trace,"one_synthetic_track_in_real_selected_cadence",config["truth_match_tolerance_channels"])
            survivals.append(record)
            write(output/f"injected_cadence_scan_{i}_catalogue.json",after_trace)
        del before_search
    np.savez_compressed(output/"mlc1_one_global_injected_track.npz",before=data,after=after,added_power=deltas,frequency_hz=frequencies,scan_start_elapsed_s=offsets,integration_s=np.array([s["integration_s"] for s in meta["scans"]]))
    write(output/"native_search_summary.json",native)
    write(output/"cadence_injection_survival.json",{
        "signal_count":1,"scan_pieces":3,"on_scan_records":survivals,
        "summary":survival_summary(survivals),
        "all_off_scans_unchanged":bool(np.array_equal(after[1::2],data[1::2])),
        "continuous_time_path_across_gaps":True,
        "global_reference_frequency_hz":global_f0,
        "injection_config":cfg,
        "injection_implementation":"Independent sampled Gaussian power in relative Hz, integration-start sampling; no smearing/beam calibration",
        "cadence_filtering_status":"not_applied; per-ON-scan recovery and timing only",
        "independence_warning":"Three ON pieces of one signal in one selected cadence, not three independent observing environments",
    })
    # Show all six observations on a genuine elapsed axis with gaps retained.
    fig,axes=plt.subplots(1,2,figsize=(12,7),layout="constrained",sharey=True)
    center0=channel-40; center1=int(channel+cfg["global_drift_hz_per_s"]*(offsets[-1]+meta["scans"][-1]["represented_duration_s"])/df)+40
    lo,hi=np.percentile(data,[1,99.5])
    for ax,array,title in zip(axes,[data,after],["Real selected cadence | before","After | one global ON-only synthetic track"]):
        ax.set_facecolor("#eeeeee")
        for i,scan in enumerate(meta["scans"]):
            extent=[center0*df/1000,(center1)*df/1000,float(offsets[i]),float(offsets[i]+scan["represented_duration_s"])]
            im=ax.imshow(array[i,:,center0:center1],extent=extent,origin="lower",aspect="auto",cmap="magma",vmin=lo,vmax=hi,interpolation="nearest")
        ax.set_ylim(0,offsets[-1]+meta["scans"][-1]["represented_duration_s"])
        ax.set_title(title,fontsize=11)
        ax.set_xlabel(f"Offset [kHz] from {frequencies[0]/1e6:.9f} MHz")
    axes[0].set_ylabel("True elapsed cadence time [s]; gray = no represented samples")
    fig.colorbar(im,ax=axes,label="Recorded power [arbitrary units]",shrink=.7)
    fig.savefig(output/"cadence_before_after.png",dpi=150)
    plt.close(fig)
    return native,survivals


def real_fixture_audit(output, config, original_config, profiles):
    before,freq,times,_=legacy.load_observation(ROOT/original_config["dataset"]["path"],original_config["dataset"])
    detector=original_config["detector"]
    control,control_trace,c=search_with_profile(before,freq,times,detector,"original_fixture_control",profiles)
    write(output/"original_fixture_coverage.json",c)
    records=[]
    for spec in config["real_fixture_synthetic_trials"]:
        injection={**original_config["injection"],**{k:v for k,v in spec.items() if k!='id'}}
        after,_,truth=legacy.inject_signal(before,freq,times,injection)
        result,trace,_=search_with_profile(after,freq,times,detector,spec["id"],profiles)
        record=survival_record(spec["id"],truth,freq,times,detector,control,result,trace,"synthetic_injection_in_original_real_Cband_fixture",config["truth_match_tolerance_channels"])
        records.append(record)
        write(output/f"fixture_{spec['id']}_catalogue.json",trace)
    summary=survival_summary(records)
    write(output/"fixture_survival.json",{"summary":summary,"records":records})
    return c,records,summary


def gaussian_fixture(spec, detector, paired=False):
    nt,nf=spec["shape"]
    times=np.arange(nt,dtype=float)*spec["time_resolution_s"]
    freq=np.arange(nf,dtype=float)*spec["channel_spacing_hz"]
    before=np.random.default_rng(spec["seed"]).normal(size=(nt,nf))
    after=before.copy();truths=[]
    signals=spec["signals"] if paired else [{"id":f"line_{i:03d}","start_channel":spec["first_start_channel"]+i*spec["spacing_channels"],"drift_hz_per_s":spec["drift_hz_per_s"],"peak_power":spec["peak_power_first"]-i*spec["peak_power_decrement_per_signal"]} for i in range(spec["signal_count"])]
    for signal in signals:
        centers=freq[signal["start_channel"]]+signal["drift_hz_per_s"]*times
        after+=signal["peak_power"]*np.exp(-.5*((freq[None,:]-centers[:,None])/(spec["gaussian_sigma_channels"]*spec["channel_spacing_hz"]))**2)
        truths.append({"id":signal["id"],"start_channel_ascending":signal["start_channel"],"start_frequency_hz":float(freq[signal["start_channel"]]),"drift_hz_per_s":signal["drift_hz_per_s"],"peak_amplitude_power":signal["peak_power"]})
    cfg={**detector,"max_abs_drift_hz_per_s":spec["detector_max_abs_drift_hz_per_s"]}
    return before,after,freq,times,truths,cfg


def synthetic_stress(output, config, detector, profiles, paired=False):
    key="paired_line_suppression_fixture" if paired else "fully_synthetic_crowded_fixture"
    before,after,freq,times,truths,cfg=gaussian_fixture(config[key],detector,paired)
    control,_,_=search_with_profile(before,freq,times,cfg,key+"_control",profiles)
    result,trace,c=search_with_profile(after,freq,times,cfg,key+"_after",profiles)
    records=[survival_record(t["id"],t,freq,times,cfg,control,result,trace,"fully_synthetic_seeded_noise_and_signals",config["truth_match_tolerance_channels"]) for t in truths]
    # Verify this run does not count a single candidate as two recovered truths.
    collisions=[]
    df=legacy.channel_spacing(freq)
    for row in trace["retained_candidates"]:
        matches=[t["id"] for t in truths if matching_rows([row],t,times,df,config["truth_match_tolerance_channels"])]
        if len(matches)>1:collisions.append({"peak_id":row["peak_id"],"truth_ids":matches})
    if collisions:
        raise AssertionError("Ambiguous multi-truth assignment; do not report duplicate recoveries")
    summary={"source_kind":"fully_synthetic", "configuration":config[key],"summary":survival_summary(records),"catalogue_summary":trace["summary"],"duplicate_truth_assignment_conflicts":collisions,"records":records}
    write(output/f"{key}.json",summary)
    write(output/f"{key}_catalogue.json",trace)
    np.savez_compressed(output/f"{key}.npz",before=before,after=after,frequency_hz=freq,time_s=times)
    return summary


def report(output,summary):
    c=summary["original_coverage"]
    native=summary["native_scans"]
    lines=["# Complete-cadence access pilot and pipeline-loss audit", "", "This report separates real observational access, blind native searches, injections into real data, and fully synthetic engineering stress tests.", "", "## Observational access", "", f"- Eight checksum-pinned released cutouts inspected; {summary['access']['distinct_scan_sequence_count']} distinct six-scan sequences, not eight independent cadences.",f"- Structural checks: {summary['access']['all_structural_cadence_checks_passed']}; 48 scan/header records inspected.",f"- Duplicate scan-sequence cutouts: {summary['access']['same_scan_sequence_different_cutout_groups']}.",f"- Conservative target/UTC-day proxy groups: {summary['access']['conservative_target_or_utc_day_proxy_groups']}.","- Access establishes six released scan records in narrow candidate-selected frequency intervals. Full original bandwidth/integration counts and telescope logs have not been independently acquired.","- Frequency centers are reconstructed from the original header lattice under blimpy half-open slicing; the absolute convention has a disclosed one-channel uncertainty.","- The pilot is L-band; the original C-band fixture is a separate engineering control. Neither is a representative population cohort.","", "## Original reference coverage", "",f"- Common valid starts: {c['legacy_start_channel_count']}/{c['input_frequency_channels']} = {100*c['legacy_start_channel_fraction']:.6f}%.",f"- Original searched track trials: {c['legacy_searched_track_trials']:,}.",f"- Discrete per-drift boxcar-valid trials in the input: {c['valid_discrete_track_trials_over_full_input']:,}.",f"- Valid discrete trials omitted by the common guard: {c['valid_discrete_tracks_omitted_by_common_guard']:,}.","- These counts measure the detector's discrete path/boxcar domain, not Gaussian-tail signal support or an astrophysical selection volume.","", "## Blind native observational searches", "", "No native peak is labeled extraterrestrial or automatically labeled terrestrial interference.","", "| Scan | Role | Raw local maxima | Uncapped NMS | Cap losses | Retained |", "|---|---|---:|---:|---:|---:|"]
    for n in native:
        s=n["catalogue"]
        lines.append(f"| {n['scan_index']} | {n['role']} | {s['thresholded_local_maxima']} | {s['uncapped_nms_candidates']} | {s['candidates_lost_to_cap']} | {s['retained_candidates']} |")
    lines.extend(["", "Every local maximum is recorded, including its suppressor or uncapped rank. The traced capped prefix exactly reproduces the unchanged original detector. Score maps can be regenerated from pinned data/config/code; their numerical hashes are retained rather than duplicating large arrays.","", "## Synthetic survival experiments", "", f"- Original-real-background engineering cases: {summary['fixture_summary']['trials']}; outcomes: {summary['fixture_summary']['first_loss_counts']}.",f"- Fully synthetic 80-line stress test: {summary['crowded']['summary']['first_loss_counts']}.",f"- Synthetic cap audit: {summary['crowded']['catalogue_summary']['uncapped_nms_candidates']} uncapped candidates; {summary['crowded']['catalogue_summary']['candidates_lost_to_cap']} discarded by the original cap.",f"- Two-track suppression stress test: {summary['paired']['summary']['first_loss_counts']}.",f"- One global chirp injected into the real selected cadence: {len(summary['cadence_survivals'])} ON-scan pieces; {sum(r['conservative_attributable_recovery'] for r in summary['cadence_survivals'])} conservatively attributable per-scan recoveries. OFF arrays remain unchanged.","- Actual MJD scan gaps are used for the global chirp; its frequency is never reset at a new ON scan.","- These are deterministic engineering scenarios, not a randomized completeness survey. No confidence interval or transmitter-origin inference is assigned to these fractions.","", "## Signal-loss records", "", "Each injected track records domain eligibility, discrete path support, compatible searched-track availability, threshold survival, local-maximum survival, frequency suppression, and cap survival. It retains a first-loss category and checks the no-injection control for ambiguous attribution.","", "Event grouping, cadence filtering, and triage are explicitly `not_applied`. Median/MAD normalization occurs inside the baseline; its loss cannot be separately identified from threshold/noise effects in this audit. The current work does not claim those later milestones are complete.","", "## Reproduction and status", "", "Run from project root:","", "```bash", ".venv/bin/python -m research.pilot.acquire", ".venv/bin/python -m research.pilot.run", ".venv/bin/python -m pytest -q tests research/pilot/tests --junitxml=research/pilot/evidence/tests.xml", ".venv/bin/python -m research.pilot.verify", "```", "", "Final test/repeat evidence is stored separately in `research/pilot/evidence/verification.json`; this scientific report is generated before that final verification and should be read with it.","", "The original project manifest is verified before and after execution. No original source/data/result is overwritten. Acquisition timing is in `evidence/network_transfer.json`; CPU timing and memory are in `profile.json`.","", "Next work: validate source cutouts against independently obtained raw-file excerpts if possible, construct a representative complete-cadence cohort, and implement overlap-aware search/event grouping and physically integrated injection before a sensitivity claim. No LLM has been introduced."])
    (output/"REPORT.md").write_text("\n".join(lines)+"\n")


def run(output=HERE/"results/milestone_001"):
    start=time.perf_counter(); output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    original=preserved_original()
    config=json.loads((HERE/"configs/audit.json").read_text())
    reference=json.loads((ROOT/"config.json").read_text())
    profiles=[]
    access,selected=observational_access(output)
    print("All observational cutouts validated",flush=True)
    native,cadence_survivals=native_and_cadence_injection(output,selected,config,reference["detector"],profiles)
    c,fixture_records,fixture_summary=real_fixture_audit(output,config,reference,profiles)
    crowded=synthetic_stress(output,config,reference["detector"],profiles)
    paired=synthetic_stress(output,config,reference["detector"],profiles,True)
    summary={"version":config["version"],"access":{k:v for k,v in access.items() if k!='metadata_and_export_elapsed_s'},"original_coverage":{k:v for k,v in c.items() if k!='per_drift'},"native_scans":native,"fixture_summary":fixture_summary,"crowded":{k:v for k,v in crowded.items() if k!='records'},"paired":{k:v for k,v in paired.items() if k!='records'},"cadence_survivals":cadence_survivals,"preservation":preserved_original(),"config":config,"source_code_sha256":{str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),HERE/"accounting.py",HERE/"observations.py",ROOT/"pipeline.py"]}}
    write(output/"summary.json",summary)
    report(output,summary)
    profile={"total_wall_s":time.perf_counter()-start,"searches":profiles,"process_max_rss":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"rss_units":"bytes" if sys.platform=='darwin' else "KiB","platform":platform.platform(),"python":sys.version,"access_and_export_s":access['metadata_and_export_elapsed_s']}
    write(output/"profile.json",profile)
    write(output/"artifact_manifest.json",{p.name:{"sha256":digest(p),"bytes":p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file() and p.name!='artifact_manifest.json'})
    print(json.dumps({"output":str(output),"original_preserved":summary['preservation'],"fixture_outcomes":fixture_summary['first_loss_counts'],"crowded_outcomes":crowded['summary']['first_loss_counts'],"paired_outcomes":paired['summary']['first_loss_counts'],"elapsed_wall_s":profile['total_wall_s']},indent=2))
    return summary


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=HERE/"results/milestone_001")
    run(parser.parse_args().output)
