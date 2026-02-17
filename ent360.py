"""
================================================================
Enterprise Data Explorer 360 - Bank-Grade Edition
================================================================
Spec-aligned:
  - Interface.xlsx = authoritative (5 sheets)
  - 4-step matching: Deterministic -> Feed Validation -> Semantic -> Aggregation
  - all-MiniLM-L6-v2 for similarity scoring ONLY
  - Phi-3 for explanation ONLY (never decisions)
  - Lineage graph with filtering
  - Full audit logging

Usage:
  streamlit run data_explorer_360.py

Requirements:
  pip install streamlit pandas openpyxl numpy plotly networkx
  pip install torch sentence-transformers transformers
  Optional: pip install bitsandbytes accelerate
"""

import streamlit as st
import pandas as pd
import numpy as np
import re, os, json
from datetime import datetime
from collections import defaultdict

try:
    import plotly.graph_objects as go
    import networkx as nx
    GRAPH_OK = True
except ImportError:
    GRAPH_OK = False

try:
    import torch
    from sentence_transformers import SentenceTransformer, util
    ML_OK = True
except ImportError:
    ML_OK = False

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline as hf_pipeline
    LLM_OK = True
except ImportError:
    LLM_OK = False

st.set_page_config(page_title="Data Explorer 360", page_icon="", layout="wide", initial_sidebar_state="expanded")

DEVICE = "cpu"
if ML_OK and torch.cuda.is_available():
    DEVICE = "cuda"
elif ML_OK:
    torch.set_num_threads(8)

EMB_PATH = os.environ.get("EMBEDDING_MODEL_PATH", "C:/SEI/AneeshModel/all-minilm-l6-v2")
PHI3_PATH = os.environ.get("PHI3_MODEL_PATH", "C:/SEI/AneeshModel/Phi-3-mini-4k-instruct")
MAP_FILE = "interface_sql_mapping.xlsx"

#  STYLING 
st.markdown("""
<style>
.hdr{background:linear-gradient(135deg,#667eea,#764ba2 50%,#f093fb);padding:2rem;border-radius:15px;text-align:center;margin-bottom:2rem;box-shadow:0 10px 30px rgba(102,126,234,.3)}
.hdr h1{font-size:2.5rem;font-weight:800;color:#fff;margin:0}.hdr p{color:rgba(255,255,255,.8);margin:.5rem 0 0}
.ch{background:#e8f5e9;color:#2e7d32;padding:3px 10px;border-radius:12px;font-weight:700;font-size:.8rem}
.cm{background:#fff3e0;color:#ef6c00;padding:3px 10px;border-radius:12px;font-weight:700;font-size:.8rem}
.cl{background:#fce4ec;color:#c2185b;padding:3px 10px;border-radius:12px;font-weight:700;font-size:.8rem}
.phi3{background:linear-gradient(135deg,#e8eaf6,#c5cae9);border-radius:12px;padding:1.2rem;margin:.8rem 0;border-left:5px solid #3f51b5}
.rules{background:linear-gradient(135deg,#ffecd2,#fcb69f);border-radius:12px;padding:1.2rem;margin:.8rem 0;border-left:5px solid #ff6b6b}
.atag{display:inline-block;background:#e3f2fd;color:#1565c0;padding:2px 6px;border-radius:3px;font-size:.7rem;font-family:monospace}
.stag{display:inline-block;padding:3px 8px;border-radius:5px;font-weight:600;font-size:.75rem;margin:2px}
.s1{background:#e8f5e9;color:#2e7d32}.s2{background:#e3f2fd;color:#1565c0}
.s3{background:#f3e5f5;color:#7b1fa2}.s4{background:#fff3e0;color:#e65100}
</style>
""", unsafe_allow_html=True)

#  SESSION STATE 
for k, v in {
    'nav':'overview','interface_df':None,'sql_df':None,'mapping_df':None,
    'pmim_df':None,'feeds_df':None,'audit_log':[],
    'f_src':[],'f_tgt':[],'f_type':[],'f_app':[],
}.items():
    if k not in st.session_state: st.session_state[k] = v

#  UTILITIES 
def ccol(c):
    return str(c).strip().lower().replace(" ","_").replace("/","_").replace("-","_").replace("(","").replace(")","").replace("#","num").strip("_")

def sg(row, col, default=""):
    try:
        val = row.get(col, default) if isinstance(row, dict) else getattr(row, col, default)
        return val if pd.notna(val) and str(val) not in ('nan','None','') else default
    except: return default

def norm(t):
    return t.lower().replace("_","").replace(" ","").replace("-","").strip() if isinstance(t,str) else ""

def alog(action, details):
    st.session_state.audit_log.append({"ts":datetime.now().isoformat(),"action":action,"details":details})

def apply_f(df):
    d = df.copy()
    if st.session_state.f_src and 'source_system' in d.columns: d=d[d['source_system'].isin(st.session_state.f_src)]
    if st.session_state.f_tgt and 'target_system' in d.columns: d=d[d['target_system'].isin(st.session_state.f_tgt)]
    if st.session_state.f_type and 'type' in d.columns: d=d[d['type'].isin(st.session_state.f_type)]
    if st.session_state.f_app and 'application' in d.columns: d=d[d['application'].isin(st.session_state.f_app)]
    return d

#  MODELS 
@st.cache_resource(show_spinner=False)
def load_emb():
    if not ML_OK: return None
    try: return SentenceTransformer(EMB_PATH, device=DEVICE)
    except Exception as e: st.warning(f"Embedding: {e}"); return None

@st.cache_resource(show_spinner=False)
def load_phi3():
    if not LLM_OK: return None
    try:
        tok = AutoTokenizer.from_pretrained(PHI3_PATH, trust_remote_code=True)
        kw = {"torch_dtype":torch.float16,"trust_remote_code":True}
        if DEVICE=="cuda":
            try:
                from transformers import BitsAndBytesConfig
                kw["quantization_config"]=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_compute_dtype=torch.float16,bnb_4bit_quant_type="nf4")
                kw["device_map"]="auto"
            except: kw["device_map"]="auto"
        else: kw["torch_dtype"]=torch.float32
        mdl = AutoModelForCausalLM.from_pretrained(PHI3_PATH, **kw)
        if DEVICE=="cpu": mdl=mdl.to("cpu")
        return hf_pipeline("text-generation",model=mdl,tokenizer=tok,max_new_tokens=256,temperature=0.2,do_sample=True,top_p=0.9,repetition_penalty=1.1)
    except Exception as e: st.warning(f"Phi-3: {e}"); return None

with st.sidebar:
    st.markdown("### Model Status")
    with st.spinner("Loading..."):
        emb_model = load_emb()
        phi3_pipe = load_phi3()
    st.success("MiniLM ready") if emb_model else st.warning("Embedding N/A")
    st.success("Phi-3 ready") if phi3_pipe else st.info("Phi-3 N/A (rule fallback)")

#  PHI-3 ENGINE 
def phi3(prompt, label="exp"):
    if phi3_pipe is None: return None
    try:
        fmt = f"<|system|>\nYou are a senior data engineer in regulated banking/asset management. Be concise. Focus on business meaning, data flow, risk. Do NOT change scores or decisions.<|end|>\n<|user|>\n{prompt}<|end|>\n<|assistant|>\n"
        r = phi3_pipe(fmt, return_full_text=False)
        txt = r[0]['generated_text'].strip()
        alog("phi3",{"label":label,"plen":len(prompt),"rlen":len(txt)})
        return txt
    except: return None

def biz_explain(ir, sr, tables, analysis):
    app=sg(ir,'application','system'); integ=sg(ir,'integration','interface')
    desc=sg(ir,'description',''); src=sg(ir,'source_system','source')
    tgt=sg(ir,'target_system','target'); dirn=sg(ir,'inbound_outbound','')
    qn=sg(sr,'queryname','query')

    p = f"Explain business purpose:\nInterface: {integ}\nApp: {app}\nDesc: {desc}\nSource: {src} -> Target: {tgt}\nDirection: {dirn}\nSQL: {qn}\nTables: {', '.join(tables[:5]) if tables else 'N/A'}\nComplexity: {analysis.get('complexity','?')}\n\nProvide: 1) Business purpose 2) Data flow 3) Value 4) Risks"
    r = phi3(p, "biz")
    if r: return r, "phi3"

    exp = f"**Business Purpose:** {desc or f'Interface ({integ}) transfers data {src} -> {tgt}.'}\n\n"
    exp += f"**Data Flow:** From {app}"
    if dirn: exp += f" ({dirn})"
    if tables: exp += f", {len(tables)} table(s): {', '.join(tables[:3])}"
    exp += ".\n\n**Value:** "
    ql = qn.lower()
    if any(w in ql for w in ['customer','client','account']): exp+="CRM and account tracking."
    elif any(w in ql for w in ['transaction','trade','payment']): exp+="Transaction processing."
    elif any(w in ql for w in ['position','holding','portfolio']): exp+="Portfolio management."
    elif any(w in ql for w in ['balance','reconciliation']): exp+="Balance tracking and reconciliation."
    else: exp+="Critical data integration."
    return exp, "rules"

def tech_explain(sr, tables, analysis):
    qn=sg(sr,'queryname','Query'); sqlt=sg(sr,'sqltext',''); sys_=sg(sr,'system','')
    if sqlt and len(sqlt)>30:
        p = f"Explain this SQL in banking context:\nQuery: {qn}\nSystem: {sys_}\nSQL:\n{sqlt[:1500]}\n\nProvide: 1) What it retrieves 2) Key joins 3) CASE WHEN logic 4) Risks"
        r = phi3(p, "tech")
        if r: return r, "phi3"

    exp = f"**Query:** `{qn}`\n"
    if sys_: exp += f"**System:** {sys_}\n"
    exp += f"**Complexity:** {analysis.get('complexity','?')}\n\n"
    if tables: exp += f"**Tables:** {', '.join(f'`{t}`' for t in tables[:5])}\n\n"
    if analysis.get('joins'): exp += f"- {len(analysis['joins'])} join(s)\n"
    if analysis.get('has_subquery'): exp += "- Subqueries\n"
    if analysis.get('has_group_by'): exp += "- Aggregation\n"
    if analysis.get('has_case_when'): exp += "- CASE WHEN logic\n"
    return exp, "rules"

def case_explain(blocks):
    if not blocks or not phi3_pipe: return None
    return phi3(f"Explain these CASE WHEN blocks in business terms:\n\n"+"\n\n".join(blocks[:3]), "case")

def risk_explain(ir, analysis):
    if not phi3_pipe: return None
    return phi3(f"Analyze risks:\nInterface: {sg(ir,'integration')}\n{sg(ir,'source_system')}->{sg(ir,'target_system')}\nTables: {','.join(analysis.get('tables',[])[:5])}\nComplexity: {analysis.get('complexity','?')}\n\nIdentify: data quality, regulatory, operational risks, recommendations", "risk")

#  SQL ANALYSIS 
def analyze_sql(sql):
    a = {'tables':[],'joins':[],'has_subquery':False,'has_union':False,'has_group_by':False,'has_order_by':False,'has_case_when':False,'case_when_blocks':[],'complexity':'Low','where_conditions':''}
    if not sql or not isinstance(sql,str): return a
    up = sql.upper()
    a['tables'] = list(set(t.strip() for t in re.findall(r'FROM\s+([^\s,;()\n]+)',up)+re.findall(r'JOIN\s+([^\s,;()\n]+)',up) if t.strip()))
    a['joins'] = re.findall(r'\bJOIN\b',up)
    a['has_subquery'] = '(SELECT' in up or up.strip().startswith('WITH ')
    a['has_union'] = 'UNION' in up
    a['has_group_by'] = 'GROUP BY' in up
    a['has_case_when'] = 'CASE' in up and 'WHEN' in up
    a['case_when_blocks'] = re.findall(r'CASE\s+.*?END',sql,re.IGNORECASE|re.DOTALL)[:3]
    wh = re.search(r'WHERE\s+(.+?)(?:GROUP BY|ORDER BY|LIMIT|HAVING|$)',up,re.DOTALL)
    if wh: a['where_conditions']=wh.group(1)[:300]
    sc = len(a['tables'])*2+len(a['joins'])*3+(10 if a['has_subquery'] else 0)+(5 if a['has_group_by'] else 0)+(5 if a['has_union'] else 0)+(5 if a['has_case_when'] else 0)
    a['complexity'] = 'High' if sc>=25 else ('Medium' if sc>=10 else 'Low')
    return a

#  DATA LOADING 
def load_ifile(file):
    xls = pd.ExcelFile(file); sheets = xls.sheet_names
    st.info(f"Sheets: {', '.join(sheets)}")

    idf = None
    for name in ['Interface','interface','Interfaces','Sheet1']:
        if name in sheets:
            idf = pd.read_excel(file, sheet_name=name)
            idf.columns = [ccol(c) for c in idf.columns]
            idf = idf.dropna(axis=1, how='all')
            idf = idf.loc[:, ~idf.columns.str.contains("^unnamed")]
            for std, vs in {
                'application':['application','app'],'integration':['integration','interface','interfacename','interface_name'],
                'description':['description','desc','interfacedescription','interface_description'],
                'type':['type'],'source_system':['source_system','source','sourcesystem'],
                'target_system':['target_system','target','targetsystem'],
                'inbound_outbound':['inbound_outbound','inbound_outbound_with_respect_to_existing_acct_platform','integrationdirection','integration_direction','direction'],
                'frequency':['frequency'],'owner':['application_owner_contact','owner','contact'],
            }.items():
                for v in vs:
                    if v in idf.columns and std not in idf.columns: idf[std]=idf[v]; break
            for col in idf.select_dtypes(include=['object']).columns:
                idf[col]=idf[col].astype(str).str.strip().replace({'nan':'','None':'','NaN':''})
            st.success(f"Interface: {len(idf)} rows ('{name}')"); alog("load_interface",{"sheet":name,"rows":len(idf)}); break
    if idf is None: st.error("Interface sheet not found"); return None,None,None

    pmim = None
    for name in ['PMIMCurrentSystem','PMIM','Systems','CurrentSystem']:
        if name in sheets:
            pmim=pd.read_excel(file,sheet_name=name); pmim.columns=[ccol(c) for c in pmim.columns]
            st.info(f"PMIM: {len(pmim)} systems"); alog("load_pmim",{"rows":len(pmim)}); break

    feeds = None
    for name in ['PB_Files_Feeds_ORIG','PB_Files_Feeds','Feeds','Files_Feeds']:
        if name in sheets:
            feeds=pd.read_excel(file,sheet_name=name); feeds.columns=[ccol(c) for c in feeds.columns]
            st.info(f"Feeds: {len(feeds)} records"); alog("load_feeds",{"rows":len(feeds)}); break

    return idf, pmim, feeds

def load_sfile(file):
    for sh in ["Queries","Sheet1","SQL","Output"]:
        try: df=pd.read_excel(file,sheet_name=sh); st.success(f"SQL: {len(df)} queries ('{sh}')"); break
        except: continue
    else: df=pd.read_excel(file)
    df.columns=[ccol(c) for c in df.columns]
    for std,vs in {'system':['system'],'file':['file','filename'],'queryname':['queryname','query_name','query'],'tables':['tables','table'],'selectcolumnscount':['selectcolumnscount','select_columns_count'],'selectcolumns':['selectcolumns','select_columns'],'sqltext':['sqltext','sql_text','sql','query_text'],'type':['type']}.items():
        for v in vs:
            if v in df.columns and std not in df.columns: df[std]=df[v]; break
    for col in df.select_dtypes(include=['object']).columns:
        df[col]=df[col].astype(str).str.strip().replace({'nan':'','None':''})
    alog("load_sql",{"rows":len(df)}); return df

#  4-STEP ENGINE 

def step1(ir, sr):
    s=0; d=[]
    app=norm(sg(ir,'application')); integ=norm(sg(ir,'integration')); desc=norm(sg(ir,'description'))
    src=norm(sg(ir,'source_system')); itype=norm(sg(ir,'type'))
    qn=norm(sg(sr,'queryname')); sf=norm(sg(sr,'file')); ssys=norm(sg(sr,'system'))
    stbl=norm(sg(sr,'tables')); stype=norm(sg(sr,'type'))

    if app and ssys and (app==ssys or app in ssys or ssys in app): s+=15; d.append(f"App matches System ({app})")
    if integ:
        iw=set(integ.split())
        if qn and (integ in qn or qn in integ): s+=15; d.append("InterfaceName~QueryName")
        elif qn:
            c=iw&set(qn.split())
            if c: s+=min(len(c)*4,10); d.append(f"InterfaceName words in QN ({len(c)})")
        if sf and (integ in sf or sf in integ): s+=5; d.append("InterfaceName~FileName")
        elif sf:
            c=iw&set(sf.split())
            if c: s+=min(len(c)*2,5); d.append(f"InterfaceName words in FN ({len(c)})")
    if src and stbl and src in stbl: s+=10; d.append("SourceSystem in Tables")
    if itype and stype and (itype==stype or itype in stype): s+=5; d.append("Type match")
    if desc and qn:
        c=set(desc.split())&set(qn.split())
        if c: s+=min(len(c)*2,10); d.append(f"Desc words in QN ({len(c)})")
    return min(s,60), d

def step2(ir, feeds):
    if feeds is None or feeds.empty: return 0, ["No feeds sheet"]
    pen=0; d=[]; src=sg(ir,'source_system','').lower(); tgt=sg(ir,'target_system','').lower(); dirn=sg(ir,'inbound_outbound','').lower()
    matched=feeds[feeds.apply(lambda f:(src and src in str(sg(f,'source_system','')).lower()) or (tgt and tgt in str(sg(f,'target_system','')).lower()),axis=1)]
    if matched.empty: return 0,["No matching feed"]
    for _,f in matched.iterrows():
        fd=str(sg(f,'inbound_outbound_with_respect_to_addv','')).lower() or str(sg(f,'in_out_with_respect_to_app','')).lower()
        if dirn and fd:
            if ('inbound' in dirn and 'outbound' in fd) or ('outbound' in dirn and 'inbound' in fd):
                pen=-10; d.append("DOWNGRADE: direction mismatch"); break
            else: d.append("Feed direction OK")
        flow=str(sg(f,'direct_indirect_feeds_flow','')).lower()
        if flow: d.append(f"Flow: {flow}")
    return pen, d

def step3(ii, si, ie, se):
    if ie is None or se is None: return 0,["Semantic N/A"],0.0
    try:
        sim=float(np.dot(ie[ii],se[si]))
        if sim>=.85: return 25,[f"Excellent ({sim:.3f})"],sim
        elif sim>=.75: return 20,[f"Very high ({sim:.3f})"],sim
        elif sim>=.65: return 15,[f"High ({sim:.3f})"],sim
        elif sim>=.55: return 10,[f"Good ({sim:.3f})"],sim
        elif sim>=.45: return 5,[f"Moderate ({sim:.3f})"],sim
        return 0,[f"Low ({sim:.3f})"],sim
    except: return 0,["Error"],0.0

def step4(s1,s2,s3,d1,d2,d3,sim):
    raw=s1+s2+s3; final=max(0,min(100,raw))
    if s1>=30 and final>=70: conf="HIGH"
    elif s1>=15 and final>=45: conf="MEDIUM"
    else: conf="LOW"
    ad = [f"<span class='stag s1'>S1 Deterministic: {s1}/60</span>"]+[f"  {x}" for x in d1]+\
         [f"<span class='stag s2'>S2 Feed: {s2}</span>"]+[f"  {x}" for x in d2]+\
         [f"<span class='stag s3'>S3 Semantic: {s3}/25 (sim={sim:.3f})</span>"]+[f"  {x}" for x in d3]+\
         [f"<span class='stag s4'>S4 Final: {final}/100 -> {conf}</span>"]
    return final, conf, ad

#  MAPPING 
def gen_mapping(idf, sdf, feeds, pmim, min_sc=40, use_sem=True):
    results=[]; st.write(f"Interfaces: {len(idf)} | SQL: {len(sdf)} | Semantic: {'ON' if use_sem and emb_model else 'OFF'}")

    ie=se=None
    if use_sem and emb_model:
        st.write("Computing embeddings...")
        it=[f"{sg(r,'application')} {sg(r,'integration')} {sg(r,'description')}".strip() or "unknown" for _,r in idf.iterrows()]
        st_=[f"{sg(r,'queryname')} {sg(r,'file')} {str(sg(r,'sqltext',''))[:200]}".strip() or "unknown" for _,r in sdf.iterrows()]
        ie=emb_model.encode(it,batch_size=32,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
        se=emb_model.encode(st_,batch_size=32,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
        st.success("Embeddings ready")

    prog=st.progress(0); mc=0; total=len(idf)
    for idx,(_,ir) in enumerate(idf.iterrows()):
        prog.progress((idx+1)/total)
        for si,(_,sr) in enumerate(sdf.iterrows()):
            s1,d1=step1(ir,sr)
            s2,d2=step2(ir,feeds)
            s3,d3,sim=step3(idx,si,ie,se)
            final,conf,ad=step4(s1,s2,s3,d1,d2,d3,sim)
            if final>=min_sc:
                mc+=1
                results.append({
                    'application':sg(ir,'application'),'integration':sg(ir,'integration'),
                    'description':sg(ir,'description'),'type':sg(ir,'type'),
                    'source_system':sg(ir,'source_system'),'target_system':sg(ir,'target_system'),
                    'inbound_outbound':sg(ir,'inbound_outbound'),
                    'sql_system':sg(sr,'system'),'sql_file':sg(sr,'file'),
                    'queryname':sg(sr,'queryname'),'tables':sg(sr,'tables'),
                    'sqltext':sg(sr,'sqltext',''),
                    'step1_score':s1,'step2_score':s2,'step3_score':s3,
                    'semantic_similarity':round(sim,4),'final_score':final,
                    'confidence':conf,'match_details':'\n'.join(ad),
                })
                alog("match",{"intf":sg(ir,'integration'),"qry":sg(sr,'queryname'),"s1":s1,"s2":s2,"s3":s3,"sim":round(sim,4),"final":final,"conf":conf})
    prog.empty(); st.success(f"Found {mc} matches")
    df=pd.DataFrame(results)
    if df.empty:
        df=pd.DataFrame(columns=['application','integration','description','type','source_system','target_system','inbound_outbound','sql_system','sql_file','queryname','tables','sqltext','step1_score','step2_score','step3_score','semantic_similarity','final_score','confidence','match_details'])
    return df

#  LINEAGE GRAPH 
def build_graph(mdf):
    if not GRAPH_OK or mdf is None or mdf.empty: st.warning("Graph needs plotly/networkx and data"); return
    G=nx.DiGraph()
    for _,r in mdf.iterrows():
        integ=sg(r,'integration','?'); src=sg(r,'source_system','?src'); tgt=sg(r,'target_system','?tgt')
        qn=sg(r,'queryname',''); tbls=sg(r,'tables','')
        G.add_node(integ,ntype='interface',color='#667eea')
        G.add_node(src,ntype='source',color='#48bb78')
        G.add_node(tgt,ntype='target',color='#ed8936')
        G.add_edge(integ,src); G.add_edge(integ,tgt)
        if qn:
            G.add_node(qn,ntype='sql',color='#9f7aea')
            G.add_edge(tgt if tgt!='?tgt' else src,qn)
            for t in str(tbls).split(',')[:5]:
                t=t.strip()
                if t and t!='nan':
                    G.add_node(t,ntype='table',color='#fc8181')
                    G.add_edge(qn,t)
    if not G.nodes: return
    pos=nx.spring_layout(G,k=2,iterations=50,seed=42)
    ex,ey=[],[]
    for u,v in G.edges():
        x0,y0=pos[u];x1,y1=pos[v];ex+=[x0,x1,None];ey+=[y0,y1,None]
    et=go.Scatter(x=ex,y=ey,mode='lines',line=dict(width=1,color='#cbd5e0'),hoverinfo='none')
    nx_,ny_,nt_,nc_,ns_=[],[],[],[],[]
    sizes={'interface':25,'source':20,'target':20,'sql':18,'table':14}
    for n in G.nodes():
        x,y=pos[n];nx_.append(x);ny_.append(y)
        nt_.append(f"{n}<br>{G.nodes[n].get('ntype','')}")
        nc_.append(G.nodes[n].get('color','#a0aec0'))
        ns_.append(sizes.get(G.nodes[n].get('ntype',''),12))
    nt=go.Scatter(x=nx_,y=ny_,mode='markers+text',marker=dict(size=ns_,color=nc_,line=dict(width=1,color='white')),text=[n for n in G.nodes()],textposition='top center',textfont=dict(size=9),hovertext=nt_,hoverinfo='text')
    fig=go.Figure(data=[et,nt],layout=go.Layout(title="Lineage: Interface -> Source -> Target -> SQL -> Tables",showlegend=False,hovermode='closest',xaxis=dict(showgrid=False,zeroline=False,showticklabels=False),yaxis=dict(showgrid=False,zeroline=False,showticklabels=False),height=600,margin=dict(l=20,r=20,t=50,b=20),paper_bgcolor='#f7fafc',plot_bgcolor='#f7fafc'))
    st.plotly_chart(fig,use_container_width=True)
    st.caption(f"Nodes: {len(G.nodes)} | Edges: {len(G.edges)}")

#  OVERVIEW PAGE 
def render_overview():
    st.markdown('<div class="hdr"><h1>Data Explorer 360</h1><p>Bank-Grade Semantic Lineage</p></div>',unsafe_allow_html=True)
    idf=apply_f(st.session_state.interface_df); mdf=st.session_state.mapping_df
    fc=sum(len(v) for v in [st.session_state.f_src,st.session_state.f_tgt,st.session_state.f_type,st.session_state.f_app])
    if fc: st.info(f"Filters active: {fc} | Showing {len(idf)}/{len(st.session_state.interface_df)} interfaces")

    c1,c2,c3,c4,c5=st.columns(5)
    with c1: st.metric("Interfaces",len(idf))
    with c2: st.metric("SQL Queries",len(st.session_state.sql_df) if st.session_state.sql_df is not None else 0)
    with c3: st.metric("Mappings",len(mdf) if mdf is not None else 0)
    with c4: st.metric("High Conf",len(mdf[mdf['confidence']=='HIGH']) if mdf is not None and 'confidence' in mdf.columns else 0)
    with c5: st.metric("Audit Log",len(st.session_state.audit_log))

    t1,t2,t3,t4,t5=st.tabs(["Mapping Results","Lineage Graph","Interface Explorer","Audit Log","Phi-3 Insights"])

    with t1:
        if mdf is not None and not mdf.empty:
            cf=st.multiselect("Confidence",["HIGH","MEDIUM","LOW"],default=["HIGH","MEDIUM","LOW"])
            fd=mdf[mdf['confidence'].isin(cf)]
            if st.session_state.f_src: fd=fd[fd['source_system'].isin(st.session_state.f_src)]
            if st.session_state.f_tgt: fd=fd[fd['target_system'].isin(st.session_state.f_tgt)]
            st.write(f"{len(fd)} mappings")
            cc=st.columns(3)
            with cc[0]: st.metric("HIGH",len(fd[fd['confidence']=='HIGH']))
            with cc[1]: st.metric("MEDIUM",len(fd[fd['confidence']=='MEDIUM']))
            with cc[2]: st.metric("LOW",len(fd[fd['confidence']=='LOW']))
            dcols=[c for c in ['integration','application','source_system','target_system','queryname','sql_file','final_score','confidence','step1_score','step2_score','step3_score','semantic_similarity'] if c in fd.columns]
            st.dataframe(fd[dcols].sort_values('final_score',ascending=False),use_container_width=True,height=400)
            st.markdown("---"); st.subheader("Match Details")
            for _,row in fd.head(20).iterrows():
                with st.expander(f"{sg(row,'integration')} <-> {sg(row,'queryname')} (Score:{sg(row,'final_score')}, {sg(row,'confidence')})"):
                    c1,c2=st.columns(2)
                    with c1: st.markdown("**Interface**"); st.write(f"App: {sg(row,'application')}"); st.write(f"Source: {sg(row,'source_system')}"); st.write(f"Target: {sg(row,'target_system')}"); st.write(f"Type: {sg(row,'type')}")
                    with c2: st.markdown("**SQL**"); st.write(f"System: {sg(row,'sql_system')}"); st.write(f"File: {sg(row,'sql_file')}"); st.write(f"Query: {sg(row,'queryname')}"); st.write(f"Tables: {sg(row,'tables')}")
                    st.markdown("**Scoring**"); st.markdown(sg(row,'match_details',''),unsafe_allow_html=True)
        else: st.info("Generate mappings first via sidebar.")

    with t2:
        if mdf is not None and not mdf.empty: build_graph(mdf)
        else: st.info("Generate mappings to see lineage graph.")

    with t3:
        srch=st.text_input("Search","")
        disp=idf
        if srch: disp=idf[idf.apply(lambda r:srch.lower() in str(r.values).lower(),axis=1)]
        st.dataframe(disp,use_container_width=True,height=400)

    with t4:
        st.caption("All decisions, scores, Phi-3 calls logged for governance.")
        if st.session_state.audit_log:
            adf=pd.DataFrame(st.session_state.audit_log)
            st.dataframe(adf,use_container_width=True,height=400)
            if st.button("Export Audit JSON"):
                adf.to_json("audit_log.json",orient='records',indent=2)
                st.success("Saved audit_log.json")
        else: st.info("No entries yet.")

    with t5:
        st.subheader("Phi-3 Insights")
        if phi3_pipe: st.success("Phi-3 available for explanations")
        else: st.warning(f"Phi-3 not loaded. Path: {PHI3_PATH}"); st.info("Using rule-based fallback")
        if mdf is not None and not mdf.empty:
            st.markdown("---")
            sel=st.selectbox("Select mapping",range(min(20,len(mdf))),format_func=lambda i:f"{sg(mdf.iloc[i],'integration')} <-> {sg(mdf.iloc[i],'queryname')} ({sg(mdf.iloc[i],'confidence')})")
            if st.button("Generate Explanation"):
                row=mdf.iloc[sel]; rd=row.to_dict()
                tbls=str(sg(row,'tables','')).split(',')
                sqlt=sg(row,'sqltext','')
                an=analyze_sql(sqlt) if sqlt else {'tables':tbls,'complexity':'Unknown','joins':[],'has_subquery':False,'has_group_by':False,'has_case_when':False,'case_when_blocks':[]}

                c1,c2=st.columns(2)
                with c1:
                    st.markdown("**Business Explanation**")
                    bx,bs=biz_explain(rd,rd,tbls,an)
                    cls="phi3" if bs=="phi3" else "rules"; lbl="Phi-3 AI" if bs=="phi3" else "Rule-Based"
                    st.markdown(f'<div class="{cls}"><small class="atag">{lbl}</small><br><br>{bx}</div>',unsafe_allow_html=True)
                with c2:
                    st.markdown("**Technical Explanation**")
                    tx,ts=tech_explain(rd,tbls,an)
                    cls="phi3" if ts=="phi3" else "rules"; lbl="Phi-3 AI" if ts=="phi3" else "Rule-Based"
                    st.markdown(f'<div class="{cls}"><small class="atag">{lbl}</small><br><br>{tx}</div>',unsafe_allow_html=True)

                if an.get('case_when_blocks'):
                    st.markdown("**CASE WHEN Logic**")
                    cx=case_explain(an['case_when_blocks'])
                    if cx: st.markdown(f'<div class="phi3"><small class="atag">Phi-3 AI</small><br><br>{cx}</div>',unsafe_allow_html=True)
                    else: st.info("CASE WHEN explanation requires Phi-3")

                st.markdown("**Risk Analysis**")
                rx=risk_explain(rd,an)
                if rx: st.markdown(f'<div class="phi3"><small class="atag">Phi-3 AI Annotation</small><br><br>{rx}</div>',unsafe_allow_html=True)
                else: st.info("Risk analysis requires Phi-3")

#  MAIN 
def main():
    st.sidebar.title("Data Explorer 360")
    st.sidebar.markdown("---")
    with st.sidebar.expander("Upload Data",expanded=st.session_state.interface_df is None):
        uf=st.file_uploader("Interface.xlsx",type=["xlsx","xls"],key="iup")
        if uf:
            with st.spinner("Loading..."): idf,pmim,feeds=load_ifile(uf)
            if idf is not None: st.session_state.interface_df=idf; st.session_state.pmim_df=pmim; st.session_state.feeds_df=feeds
        sf=st.file_uploader("SqlOutput.xls",type=["xlsx","xls"],key="sup")
        if sf:
            with st.spinner("Loading..."): st.session_state.sql_df=load_sfile(sf)

    if st.session_state.interface_df is not None and st.session_state.sql_df is not None:
        st.sidebar.markdown("---"); st.sidebar.subheader("Matching")
        usem=st.sidebar.checkbox("Semantic (MiniLM)",value=emb_model is not None,disabled=emb_model is None)
        msc=st.sidebar.slider("Min Score",20,100,40,5)
        if st.sidebar.button("Generate Mapping",use_container_width=True):
            with st.spinner("Running 4-step engine..."):
                st.session_state.mapping_df=gen_mapping(apply_f(st.session_state.interface_df),st.session_state.sql_df,st.session_state.feeds_df,st.session_state.pmim_df,msc,usem)
                if st.session_state.mapping_df is not None and not st.session_state.mapping_df.empty:
                    try: st.session_state.mapping_df.to_excel(MAP_FILE,index=False); st.sidebar.success(f"Saved {MAP_FILE}")
                    except: pass
            st.rerun()

    if st.session_state.interface_df is not None:
        st.sidebar.markdown("---"); st.sidebar.subheader("Global Filters")
        df=st.session_state.interface_df
        if 'source_system' in df.columns:
            o=sorted([s for s in df['source_system'].dropna().unique() if s]); st.session_state.f_src=st.sidebar.multiselect("Source System",o,default=st.session_state.f_src)
        if 'target_system' in df.columns:
            o=sorted([s for s in df['target_system'].dropna().unique() if s]); st.session_state.f_tgt=st.sidebar.multiselect("Target System",o,default=st.session_state.f_tgt)
        if 'type' in df.columns:
            o=sorted([s for s in df['type'].dropna().unique() if s]); st.session_state.f_type=st.sidebar.multiselect("Type",o,default=st.session_state.f_type)
        if 'application' in df.columns:
            o=sorted([s for s in df['application'].dropna().unique() if s]); st.session_state.f_app=st.sidebar.multiselect("Application",o,default=st.session_state.f_app)
        if sum(len(v) for v in [st.session_state.f_src,st.session_state.f_tgt,st.session_state.f_type,st.session_state.f_app])>0:
            if st.sidebar.button("Clear Filters",use_container_width=True):
                st.session_state.f_src=[]; st.session_state.f_tgt=[]; st.session_state.f_type=[]; st.session_state.f_app=[]; st.rerun()

    if st.session_state.interface_df is None:
        st.markdown('<div class="hdr"><h1>Data Explorer 360</h1><p>Bank-Grade Semantic Lineage & SQL Mapping</p></div>',unsafe_allow_html=True)
        st.info("Upload Interface.xlsx and SqlOutput.xls in the sidebar.")
        st.markdown("""
### Spec-Aligned Architecture

| Step | Source | Weight | Purpose |
|------|--------|--------|---------|
| **Step 1** Deterministic | Interface sheet ONLY | Major (60 pts) | App, InterfaceName, SourceSystem, Type |
| **Step 2** Feed Validation | PB_Files_Feeds | Medium (penalty) | Direction consistency, can only DOWNGRADE |
| **Step 3** Semantic | all-MiniLM-L6-v2 | Minor (25 pts) | Description/SQLText cosine similarity |
| **Step 4** Aggregation | Combined | Final score | If Step 1 fails -> confidence CANNOT be HIGH |

**Phi-3 LLM (Explanation Only - Never Decisions):**
- Business intent / Transformation logic / CASE WHEN / Derived columns / Risk
- 4-bit quantized, max 256 tokens, temp 0.2, local only

**Governance:** All decisions logged. MiniLM scores logged numerically. Phi-3 labeled "AI Annotation".
        """)
    else: render_overview()

if __name__=="__main__": main()
