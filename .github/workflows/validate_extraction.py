import json,re,sys
def resolve(s,root):
    while "$ref" in s:
        n=s["$ref"].split("/")[-1]; s=root["$defs"][n]
    return s
def tn(v):
    if v is None: return "null"
    if isinstance(v,bool): return "boolean"
    if isinstance(v,int): return "integer"
    if isinstance(v,float): return "number"
    if isinstance(v,str): return "string"
    if isinstance(v,list): return "array"
    return "object"
def tmatch(v,t):
    ts=t if isinstance(t,list) else [t]
    k=tn(v)
    return any(k==x or (x=="number" and k=="integer") for x in ts)
def val(v,s,root,path,errs):
    if "$ref" in s: return val(v,resolve(s,root),root,path,errs)
    if "anyOf" in s:
        for sub in s["anyOf"]:
            e=[]; val(v,sub,root,path,e)
            if not e: break
        else: errs.append(f"{path}: matches none of anyOf")
    for sub in s.get("allOf",[]): val(v,sub,root,path,errs)
    if "const" in s and v!=s["const"]: errs.append(f"{path}: must equal {s['const']!r}, got {v!r}")
    if "enum" in s and v not in s["enum"]: errs.append(f"{path}: {v!r} not in allowed values")
    if "type" in s and not tmatch(v,s["type"]): errs.append(f"{path}: wrong type {tn(v)}"); return
    if isinstance(v,str):
        if "pattern" in s and not re.search(s["pattern"],v): errs.append(f"{path}: {v!r} bad format")
        if "maxLength" in s and len(v)>s["maxLength"]: errs.append(f"{path}: too long ({len(v)}>{s['maxLength']})")
    if isinstance(v,(int,float)) and not isinstance(v,bool):
        if "minimum" in s and v<s["minimum"]: errs.append(f"{path}: below minimum")
        if "maximum" in s and v>s["maximum"]: errs.append(f"{path}: above maximum")
    if isinstance(v,list):
        if "minItems" in s and len(v)<s["minItems"]: errs.append(f"{path}: needs at least {s['minItems']} items")
        if "maxItems" in s and len(v)>s["maxItems"]: errs.append(f"{path}: allows at most {s['maxItems']} items")
        if "items" in s:
            for i,x in enumerate(v): val(x,s["items"],root,f"{path}[{i}]",errs)
    if isinstance(v,dict):
        for r in s.get("required",[]):
            if r not in v: errs.append(f"{path}: missing {r}")
        props=s.get("properties",{})
        if s.get("additionalProperties") is False:
            for k in v:
                if k not in props: errs.append(f"{path}: unknown field {k}")
        for k,x in v.items():
            if k in props: val(x,props[k],root,f"{path}.{k}",errs)
    if "if" in s:
        e=[]; val(v,s["if"],root,path,e)
        if not e and "then" in s: val(v,s["then"],root,path,errs)
def walk(o,f):
    if isinstance(o,dict):
        f(o)
        for x in o.values(): walk(x,f)
    elif isinstance(o,list):
        for x in o: walk(x,f)
def checks(d):
    errs=[]
    ids={k:set() for k in "SAMEPTGFC"}
    def reg(lst,key,pre):
        for x in lst:
            i=x[key]
            if i in ids[pre]: errs.append(f"duplicate id {i}")
            ids[pre].add(i)
    reg(d["sources"],"source_id","S");reg(d["actors"],"actor_id","A");reg(d["measures"],"measure_id","M")
    reg(d["timeline"],"event_id","E");reg(d["proceedings"],"proceeding_id","P");reg(d["statements"],"statement_id","T")
    reg(d["aims_and_motives"],"id","G");reg(d["reported_effects"],"effect_id","F");reg(d["conflicts_and_gaps"],"item_id","C")
    def f(o):
        for k,pre in [("source_id","S"),("actor_ids","A"),("measure_ids","M"),("proceeding_ids","P"),("related_measure_ids","M"),
                      ("imposing_actor_ids","A"),("subject_measure_ids","M"),("affected_actor_ids","A"),
                      ("speaker_actor_id","A"),("attributed_to_actor_id","A"),("initiating_actor_id","A")]:
            if k in o and o[k]:
                for i in (o[k] if isinstance(o[k],list) else [o[k]]):
                    if i not in ids[pre]: errs.append(f"dangling reference {k}={i}")
    walk(d,f)
    ep=d["episode"]
    if ep["end_date"]["value"]["iso"] and ep["ongoing_as_of"]["value"]["iso"]: errs.append("end_date and ongoing_as_of both filled")
    if ep["sanctions_imposed"]["value"]==0 and ep["sanction_imposition_start_date"]["value"]["iso"]: errs.append("imposition start filled but sanctions_imposed=0")
    if ep["unsc_involved"]["value"]==1 and ep["institution_id"]!=4400: errs.append("unsc_involved=1 but institution_id != 4400")
    if ep["institution_id"]==4580 and ep["international_institution_involved"]["value"]!=1: errs.append("institution_id 4580 but institution flag not 1")
    # case ID rule: start year + start month + 710 + target ccode (padding variants accepted)
    sd=ep["start_date"]["value"]; cid=ep["case_id"]
    if sd["iso"] and len(sd["iso"])>=7 and ep["target_cow_code"] is not None:
        y,m=sd["iso"][:4],int(sd["iso"][5:7]); t=ep["target_cow_code"]
        exp={f"{y}{m}710{t:03d}"}  # month unpadded, COW code padded to 3 digits
        flagged=any(c["kind"]=="case_id_mismatch" for c in d["conflicts_and_gaps"])
        if cid not in exp and not flagged: errs.append(f"case_id {cid} does not match expected {sorted(exp)} and no case_id_mismatch is flagged")
    for m in d["measures"]:
        if m["stage"]=="imposed" and ep["sanctions_imposed"]["value"]==0: errs.append(f"{m['measure_id']} imposed but sanctions_imposed=0")
        if m["stage"]=="threatened" and ep["threat_made"]["value"]==0: errs.append(f"{m['measure_id']} threatened but threat_made=0")
    return errs
if __name__=="__main__":
    root=json.load(open(sys.argv[1])); d=json.load(open(sys.argv[2]))
    errs=[]; val(d,root,root,"$",errs)
    if not errs: errs+=checks(d)
    print("PASS" if not errs else f"{len(errs)} problems"); [print(" -",e) for e in errs]
