import json,sys
from validate_extraction import val
ALLVARS=["issue1","issue2","econ_issue","nonecon_issue","threatsanct_type","imposesanct_type","human_rights","severity_CES","anticSender_CES","anticTarget_CES","SenderCost_CES","TargetCost_CES","smart_CES","finaloutcome","sendersettlenature","tgtsettlenature","targetcapitulate"]
NULLABLE={"issue2","threatsanct_type","imposesanct_type","finaloutcome"}
def ids_of(ex):
    s=set()
    for k,key in [("actors","actor_id"),("measures","measure_id"),("timeline","event_id"),("proceedings","proceeding_id"),("statements","statement_id"),("aims_and_motives","id"),("reported_effects","effect_id"),("conflicts_and_gaps","item_id")]:
        s|={x[key] for x in ex[k]}
    return s
def checks(cd,ex,require_all=False):
    errs=[]; info=[]
    vars_=[r["variable"] for r in cd["codes"]]
    if len(vars_)!=len(set(vars_)): errs.append("a variable is coded more than once")
    missing=[v for v in ALLVARS if v not in vars_]
    (errs if require_all else info).append(f"{len(vars_)} of {len(ALLVARS)} variables coded"+(f"; missing {missing}" if missing else ""))
    if ex and cd["extraction_ref"]["case_id"]!=ex["episode"]["case_id"]: errs.append("codes file points at a different case than the extraction")
    known=ids_of(ex) if ex else None
    byv={r["variable"]:r for r in cd["codes"]}
    for r in cd["codes"]:
        v=r["variable"]; code=r["code"]
        nums=[s["step_number"] for s in r["reasoning_steps"]]
        if nums!=list(range(1,len(nums)+1)): errs.append(f"{v}: step numbers not 1..n in order")
        if r["reasoning_steps"][-1]["step_type"]!="decide": errs.append(f"{v}: last reasoning step must be 'decide'")
        if r["insufficient_evidence"] and code is not None: errs.append(f"{v}: insufficient_evidence but a code is given")
        if code is None and not r["insufficient_evidence"] and v not in NULLABLE: errs.append(f"{v}: blank code without insufficient_evidence")
        if r["insufficient_evidence"] and not r["human_review"]["needed"]: errs.append(f"{v}: insufficient evidence must be flagged for human review")
        if r["confidence"]=="low" and not r["human_review"]["needed"]: errs.append(f"{v}: low confidence must be flagged for human review")
        if r["human_review"]["needed"] and not r["human_review"]["reason"]: errs.append(f"{v}: human review flagged without a reason")
        cs=r["candidate_codes"]
        if len(cs)==1 and not r["single_candidate_justification"]: errs.append(f"{v}: single candidate needs a justification")
        sel=[c for c in cs if c["selected"]]
        if len(sel)!=1: errs.append(f"{v}: exactly one candidate must be selected")
        elif sel[0]["code"]!=code: errs.append(f"{v}: selected candidate does not match the final code (use a null candidate for 'no code')")
        seen=[json.dumps(c["code"]) for c in cs]
        if len(seen)!=len(set(seen)): errs.append(f"{v}: duplicate candidate codes")
        if known is not None:
            refs=set(r["evidence_refs"])|{x for s in r["reasoning_steps"] for x in s["refs"]}|{x for c in cs for x in c["supporting_refs"]}
            for x in refs-known: errs.append(f"{v}: reference {x} not found in extraction")
        if v in ("threatsanct_type","imposesanct_type"):
            ms=r["measure_mappings"]; stage="threatened" if v=="threatsanct_type" else "imposed"
            if code is not None and not ms: errs.append(f"{v}: measure_mappings required")
            mapped={m["code"] for m in ms if m["code"] is not None}
            if code is not None and mapped!=set(code): errs.append(f"{v}: codes {sorted(code)} do not equal union of mappings {sorted(mapped)}")
            if ex:
                st={m["measure_id"]:m["stage"] for m in ex["measures"]}
                for m in ms:
                    if st.get(m["measure_id"])!=stage: errs.append(f"{v}: {m['measure_id']} is not a {stage} measure")
                flag=ex["episode"]["threat_made" if stage=="threatened" else "sanctions_imposed"]["value"]
                if flag==0 and code is not None: errs.append(f"{v}: coded but the extraction says none occurred")
    g=lambda n: byv[n]["code"] if n in byv else None
    if g("sendersettlenature") is not None and g("tgtsettlenature") is not None and g("sendersettlenature")+g("tgtsettlenature")!=10: errs.append("settlement scores do not sum to 10")
    if g("econ_issue")==1 and g("nonecon_issue")==1: errs.append("econ_issue and nonecon_issue are both 1")
    fo=g("finaloutcome")
    if ex and isinstance(fo,int):
        imp=ex["episode"]["sanctions_imposed"]["value"]
        if imp==0 and fo>5: errs.append("finaloutcome 6-10 requires sanctions imposed")
        if imp==1 and fo<=5: errs.append("finaloutcome 1-5 requires no sanctions imposed")
    return errs,info
if __name__=="__main__":
    args=[a for a in sys.argv if a!="--full"]
    root=json.load(open(args[1])); cd=json.load(open(args[2])); ex=json.load(open(args[3])) if len(args)>3 else None
    errs=[]; val(cd,root,root,"$",errs)
    info=[]
    if not errs: e,info=checks(cd,ex,require_all="--full" in sys.argv); errs+=e
    print("PASS" if not errs else f"{len(errs)} problems"); [print(" -",x) for x in errs]; [print(" i",x) for x in info]
