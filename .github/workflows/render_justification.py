import json,re,textwrap
import pandas as pd
from validate_codes import ALLVARS, checks
W=78
import sys
cb=None
def labels(n):
    t=cb[cb['Variable Name']==n].iloc[0]['What the variable measures']
    return {int(m.group(1)):m.group(2).strip() for m in re.finditer(r'(?m)^(\d{1,2})\. ([^:\n]+?)(?::|$)',t)}
LAB={}
Q={"issue1":"What was the main issue behind the sanctions?",
 "issue2":"Was there a second issue? (blank if none)",
 "econ_issue":"Was the main issue about the economy or trade?",
 "nonecon_issue":"Was the main issue about something other than the economy or trade?",
 "threatsanct_type":"What kinds of sanctions were threatened?",
 "imposesanct_type":"What kinds of sanctions were imposed?",
 "human_rights":"Was human rights an issue in the episode?",
 "severity_CES":"How severe was the episode, from 1 (extremely minor) to 10 (catastrophic)?",
 "anticSender_CES":"How much damage to the sender was predicted, from 1 (minor) to 3 (catastrophic)?",
 "anticTarget_CES":"How much damage to the target was predicted, from 1 (minor) to 3 (catastrophic)?",
 "SenderCost_CES":"How much damage did the sender actually suffer, from 1 (minor) to 3 (catastrophic)?",
 "TargetCost_CES":"How much damage did the target actually suffer, from 1 (minor) to 3 (catastrophic)?",
 "smart_CES":"Were the sanctions targeted ('smart') rather than aimed at the whole government?",
 "finaloutcome":"How did the episode end?",
 "sendersettlenature":"How well did the sender fare by the end? (score out of 10, shared with the target)",
 "tgtsettlenature":"How well did the target fare by the end? (score out of 10, shared with the sender)",
 "targetcapitulate":"Did the target change its behavior in response to the start of the episode?"}
BINARY={"econ_issue","nonecon_issue","human_rights","smart_CES","targetcapitulate"}
def meaning(v,c):
    if c is None: return "No code (insufficient evidence)" if v not in ("issue2",) else "None"
    if isinstance(c,list): return "; ".join(meaning(v,x) for x in c)
    if v in LAB:
        return f"{c} ({LAB[v][c]})" if c in LAB[v] else f"{c}"
    if v in BINARY: return f"{c} ({'Yes' if c==1 else 'No'})"
    if v in ("sendersettlenature","tgtsettlenature"): return f"{c} out of 10"
    return f"{c}"
def wrap(text,indent=0,first=None):
    pre=" "*indent; f=first if first is not None else pre
    return textwrap.fill(text,W,initial_indent=f,subsequent_indent=pre,break_long_words=False)
def lookup(ex,i):
    for k,key,fld in [("actors","actor_id","name"),("measures","measure_id","description"),("timeline","event_id","description"),("proceedings","proceeding_id","forum"),("statements","statement_id","content"),("aims_and_motives","id","claim"),("reported_effects","effect_id","description"),("conflicts_and_gaps","item_id","description")]:
        for x in ex[k]:
            if x[key]==i: return x[fld]
    return "(not found)"
def hdr(byv,*vs):
    parts=[]
    for v in vs:
        c=byv[v]["code"] if v in byv else None
        if c is not None and v in LAB and c in LAB[v]: parts.append(f"{LAB[v][c]} ({c})")
        elif c is not None: parts.append(f"{c}")
    return "; ".join(parts) if parts else "(not coded)"
def rule(ch="-"): return ch*W
def render(cd,ex):
    byv={r["variable"]:r for r in cd["codes"]}; ep=ex["episode"]; L=[]
    L+=["CODE JUSTIFICATION",f"CASE ID: {cd['case_id']}",f"EPISODE NAME: {ep['episode_name']}","",
        f"Date range: {ep['start_date']['value']['iso'].replace('-','/')} - {ep['end_date']['value']['iso'].replace('-','/')}","Sender: China (710)",f"Target: {ep['target_name']['value']} ({ep['target_cow_code']})",
        "Issue: "+hdr(byv,"issue1","issue2"),"Final Outcome: "+hdr(byv,"finaloutcome"),"",
        f"Prepared: {cd['run_log']['coding_date']}",f"Model: {cd['run_log']['model_name']}",
        f"Codebook: {cd['run_log']['codebook_version']} | Extraction schema: {cd['extraction_ref']['extraction_schema_version']} | Codes schema: {cd['schema_version']}","",rule("="),
        "SECTION 1. HOW TO READ THIS DOCUMENT",rule("="),""]
    L+=[wrap("This document explains, in plain language, how each judgment-based code for this case was reached. A judgment-based code is one where reasonable researchers could disagree, such as how severe an episode was or how it ended. Facts such as dates and measures are recorded separately in the case's extraction file ("+cd['case_id']+"_JSON.json)."),"",
        wrap("For each variable the document gives the code, the confidence level, whether a person should check it, the facts it rests on, the steps of reasoning, the strongest case for each option considered, and why one option was chosen."),"",
        wrap("Two cautions. First, this justification was written by an AI model. It is a written argument that can be checked against the facts it cites. It is not a record of how the model computed the code internally, and it is not proof that the code is right. Second, codes marked for human review should be confirmed by a person before they are used in analysis."),"",
        rule("="),"SECTION 2. SUMMARY OF CODES",rule("="),""]
    done=[v for v in ALLVARS if v in byv]
    for v in done:
        r=byv[v]; L.append(wrap(f"{v}: {meaning(v,r['code'])}",3,first=""))
        L.append(wrap(f"Confidence: {r['confidence']} | Human review: {'yes' if r['human_review']['needed'] else 'no'}",3,first="   "))
    miss=[v for v in ALLVARS if v not in byv]
    L+=[""]+([wrap(f"Not coded: {', '.join(miss)}.")] if miss else [])+["",rule("="),"SECTION 3. CODES THAT NEED HUMAN REVIEW",rule("="),""]
    rv=[v for v in done if byv[v]["human_review"]["needed"]]
    for v in rv: L.append(wrap(f"{v}: {byv[v]['human_review']['reason']}",2,first="- "))
    if not rv: L.append("None.")
    L+=["",rule("="),"SECTION 4. JUSTIFICATION BY VARIABLE",rule("="),""]
    for v in done:
        r=byv[v]
        L+=[v.upper()+" - "+Q[v],rule(),f"CODE: {meaning(v,r['code'])}",f"CONFIDENCE: {r['confidence']}",
            wrap("HUMAN REVIEW: "+("Yes. "+r['human_review']['reason'] if r['human_review']['needed'] else "No."),14,first=""),"",
            "CODEBOOK RULES APPLIED:"]
        L+=[wrap(c,4,first="  - ") for c in r["codebook_refs"]]
        L+=["","FACTS THIS RESTS ON:"]
        L+=[wrap(f"{lookup(ex,i)} [{i}]",4,first="  - ") for i in r["evidence_refs"]]
        L+=["","HOW THE DECISION WAS REACHED:"]
        for s in r["reasoning_steps"]:
            tag=f" [{', '.join(s['refs'])}]" if s["refs"] else ""
            L.append(wrap(s["text"]+tag,5,first=f"  {s['step_number']}. "))
        if r["measure_mappings"]:
            L+=["","HOW EACH MEASURE WAS ASSIGNED:"]
            for m in r["measure_mappings"]:
                L.append(wrap(f"{m['measure_id']} ({lookup(ex,m['measure_id'])}): {meaning(v,m['code']) if m['code'] is not None else 'not coded separately'}. {m['reason']}",4,first="  - "))
        L+=["","THE OPTIONS CONSIDERED:"]
        for k,c in enumerate(r["candidate_codes"]):
            tag="SELECTED" if c["selected"] else "not selected"
            L+=[f"  Option {chr(65+k)}: {meaning(v,c['code']) if c['code'] is not None else 'No code (insufficient evidence)'} - {tag}",
                wrap("Best argument for it: "+c["argument_for"],6,first="      "),
                wrap("Its weakest point: "+c["weakest_point"],6,first="      "),""]
        L+=["WHY THIS DECISION WAS MADE:",wrap(r["chosen_rationale"],2,first="  "),"","WHAT WOULD CHANGE IT:",wrap(r["would_change_if"],2,first="  "),"",""]
    errs,_=checks(cd,ex)
    L+=[rule("="),"SECTION 5. CONSISTENCY CHECKS",rule("="),""]
    ok=lambda b:"PASS" if b else "FAIL"
    L+=[f"Variables coded: {len(done)} of {len(ALLVARS)}",
        f"Each selected option matches its final code: {ok(not any('selected' in e for e in errs))}",
        f"Every cited fact exists in the extraction file: {ok(not any('not found' in e for e in errs))}",
        f"Sanction-type codes equal the per-measure assignments: {ok(not any('mapping' in e for e in errs))}",
        f"Low-confidence and no-code decisions are flagged for review: {ok(not any('flagged' in e for e in errs))}"]
    L.append("Settlement scores sum to 10: "+(ok(not any('sum to 10' in e for e in errs)) if 'sendersettlenature' in byv and 'tgtsettlenature' in byv else "not applicable"))
    L.append("Final outcome agrees with imposition status: "+(ok(not any('finaloutcome' in e for e in errs)) if 'finaloutcome' in byv else "not applicable (not coded)"))
    L.append("Economic and non-economic issue flags are not both 1: "+(ok(not any('both 1' in e for e in errs)) if 'econ_issue' in byv else "not applicable (not coded)"))
    L+=["",rule("="),"SECTION 6. GAPS AND CONFLICTS IN THE EVIDENCE THAT AFFECT THESE CODES",rule("="),""]
    cs=sorted({i for r in cd["codes"] for i in set(r["evidence_refs"])|{x for s in r["reasoning_steps"] for x in s["refs"]} if i.startswith("C")})
    L+=[wrap(f"{i}: {lookup(ex,i)}",5,first="- ") for i in cs] or ["None cited."]
    L+=["",rule("="),"SECTION 7. WHERE THIS APPEARS ELSEWHERE",rule("="),"",
        wrap("The reason each code was chosen also appears, in short form, in the Coding Rationale section at the end of the case narrative. The facts cited by ID are in the extraction file, and the codes themselves are in the codes file ("+cd['case_id']+"_CODES.json)."),""]
    return "\n".join(L)
if __name__=="__main__":
    if len(sys.argv)!=5: sys.exit("usage: python render_justification.py <codes.json> <extraction.json> <codebook.csv> <out.txt>")
    cd=json.load(open(sys.argv[1])); ex=json.load(open(sys.argv[2]))
    cb=pd.read_csv(sys.argv[3],dtype=str,keep_default_na=False)
    LAB.update({"issue1":labels("issue1"),"issue2":labels("issue1"),"imposesanct_type":labels("imposesanct_type"),"threatsanct_type":labels("threatsanct_type"),"finaloutcome":labels("finaloutcome")})
    open(sys.argv[4],"w",encoding="utf-8").write(render(cd,ex)); print("rendered",sys.argv[4])
