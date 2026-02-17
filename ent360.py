"""
========================================================
Enterprise Data Explorer 360° - Complete GPU Edition
========================================================
Optimized for 8x Nvidia Blackwell GPUs
Features:
✓ Multi-GPU semantic matching (All-MiniLM-L6-v2)
✓ Phi-3 AI business insights
✓ Interactive data lineage graphs
✓ Color-coded inbound/outbound flows
✓ Interface + SQL + Lineage mapping
✓ Advanced filtering and search
========================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import re
import os
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Any
import logging
from datetime import datetime
import time
import warnings
warnings.filterwarnings('ignore')

# GPU and ML
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from sentence_transformers import SentenceTransformer, util

# Visualization
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import networkx as nx

# SQL Parsing
try:
    import sqlglot
    from sqlglot.expressions import Table, Column, Join
    SQLGLOT_AVAILABLE = True
except:
    SQLGLOT_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========================================================
# GPU CONFIGURATION
# ========================================================

class GPUManager:
    """Manage single GPU with 8GB VRAM - Optimized for memory efficiency"""
    
    def __init__(self):
        self.device_count = torch.cuda.device_count()
        self.primary_device = "cuda:0" if torch.cuda.is_available() else "cpu"
        
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            memory_gb = props.total_memory / (1024**3)
            logger.info(f"🚀 GPU Detected: {props.name} ({memory_gb:.1f}GB VRAM)")
            
            # Enable memory optimizations for 8GB GPU
            torch.backends.cudnn.benchmark = True
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.cuda.empty_cache()  # Clear cache
            
            # Set memory fraction to prevent OOM
            if memory_gb <= 8.5:
                logger.info("⚙️ Enabling memory optimizations for 8GB GPU")
        else:
            logger.warning("⚠️ No GPU detected, using CPU")
    
    def get_device(self, gpu_id: int = 0):
        """Always return cuda:0 for single GPU"""
        if torch.cuda.is_available():
            return "cuda:0"
        return "cpu"
    
    def get_memory_stats(self, gpu_id: int = 0):
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated(0) / (1024**3)
            reserved = torch.cuda.memory_reserved(0) / (1024**3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            return f"Using: {allocated:.2f}GB / {total:.1f}GB (Reserved: {reserved:.2f}GB)"
        return "N/A"
    
    def clear_memory(self):
        """Clear GPU cache to free memory"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            import gc
            gc.collect()
            logger.info("🧹 GPU memory cleared")

gpu_manager = GPUManager()

# ========================================================
# STREAMLIT CONFIGURATION
# ========================================================

st.set_page_config(
    page_title="Enterprise Data Explorer 360°",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================================================
# PREMIUM STYLING
# ========================================================

st.markdown("""
<style>
    .premium-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        padding: 2.5rem;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 15px 40px rgba(102, 126, 234, 0.4);
    }
    
    .premium-title {
        font-size: 3.5rem;
        font-weight: 900;
        color: white;
        margin: 0;
        text-shadow: 3px 3px 6px rgba(0,0,0,0.3);
    }
    
    .premium-subtitle {
        font-size: 1.3rem;
        color: rgba(255,255,255,0.95);
        margin-top: 0.5rem;
    }
    
    .gpu-badge {
        display: inline-block;
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
        padding: 0.6rem 1.5rem;
        border-radius: 25px;
        font-weight: 700;
        font-size: 0.95rem;
        box-shadow: 0 4px 15px rgba(17, 153, 142, 0.3);
        margin: 0.5rem;
    }
    
    .metric-card {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        text-align: center;
        transition: all 0.3s ease;
        border-top: 5px solid #667eea;
    }
    
    .metric-card:hover {
        transform: translateY(-10px);
        box-shadow: 0 15px 40px rgba(102, 126, 234, 0.25);
    }
    
    .metric-value {
        font-size: 3.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0.5rem 0;
    }
    
    .metric-label {
        font-size: 1.1rem;
        color: #666;
        font-weight: 500;
        text-transform: uppercase;
    }
    
    .interactive-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 6px solid #667eea;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .interactive-card:hover {
        transform: translateX(12px);
        box-shadow: 0 8px 30px rgba(102, 126, 234, 0.2);
    }
    
    .flow-inbound {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem 1.2rem;
        border-radius: 20px;
        font-weight: 700;
        display: inline-block;
        font-size: 0.9rem;
    }
    
    .flow-outbound {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 0.5rem 1.2rem;
        border-radius: 20px;
        font-weight: 700;
        display: inline-block;
        font-size: 0.9rem;
    }
    
    .flow-bidirectional {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
        padding: 0.5rem 1.2rem;
        border-radius: 20px;
        font-weight: 700;
        display: inline-block;
        font-size: 0.9rem;
    }
    
    .confidence-high {
        background: linear-gradient(135deg, #38ef7d 0%, #11998e 100%);
        color: white;
        padding: 0.5rem 1.2rem;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    
    .confidence-medium {
        background: linear-gradient(135deg, #FFD26F 0%, #FF9800 100%);
        color: white;
        padding: 0.5rem 1.2rem;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    
    .confidence-low {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
        color: white;
        padding: 0.5rem 1.2rem;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    
    .ai-insight {
        background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
        border-radius: 15px;
        padding: 2rem;
        margin: 2rem 0;
        border-left: 8px solid #ff6b6b;
    }
    
    .filter-panel {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-left: 5px solid #2196f3;
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1.5rem 0;
    }
    
    .system-badge {
        display: inline-block;
        background: #e3f2fd;
        color: #1976d2;
        padding: 0.4rem 1rem;
        border-radius: 15px;
        margin: 0.3rem;
        font-size: 0.9rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ========================================================
# SESSION STATE
# ========================================================

def initialize_session_state():
    defaults = {
        'navigation_level': 'overview',
        'selected_source': None,
        'selected_target': None,
        'selected_interface': None,
        'interface_df': None,
        'pmim_df': None,
        'pbfile_df': None,
        'sql_df': None,
        'mapping_df': None,
        'lineage_graph': None,
        'filter_source': [],
        'filter_target': [],
        'filter_flow_direction': [],
        'filter_application': [],
        'filter_type': [],
        'embedding_model': None,
        'llm_model': None,
        'llm_tokenizer': None,
        'embeddings_cache': {}
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

# ========================================================
# MODEL LOADING
# ========================================================

@st.cache_resource(show_spinner=False)
def load_embedding_model():
    try:
        logger.info("Loading All-MiniLM-L6-v2 (optimized for 8GB GPU)")
        device = gpu_manager.get_device(0)
        
        model_path = "C:/SEI/AneeshModel/all-minilm-l6-v2"
        if not os.path.exists(model_path):
            model_path = "sentence-transformers/all-MiniLM-L6-v2"
        
        # Load model with memory optimization
        model = SentenceTransformer(model_path, device=device)
        
        # Clear cache after loading
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logger.info(f"✅ Embedding model loaded on {device}")
        logger.info(f"   {gpu_manager.get_memory_stats()}")
        return model
    except Exception as e:
        logger.error(f"❌ Embedding load failed: {e}")
        return None

@st.cache_resource(show_spinner=False)
def load_llm_model():
    try:
        logger.info("Loading Phi-3 with 4-bit quantization (optimized for 8GB GPU)")
        device = gpu_manager.get_device(0)
        
        model_path = "C:/SEI/AneeshModel/phi-3-mini-4k-instruct"
        if not os.path.exists(model_path):
            model_path = "microsoft/Phi-3-mini-4k-instruct"
        
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        
        # Use 4-bit quantization to fit in 8GB VRAM
        # This reduces memory from ~8GB to ~2GB
        from transformers import BitsAndBytesConfig
        
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4"
        )
        
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            quantization_config=quantization_config,
            device_map="auto",
            trust_remote_code=True,
            low_cpu_mem_usage=True
        )
        
        # Clear cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logger.info(f"✅ Phi-3 loaded (4-bit quantized) on {device}")
        logger.info(f"   {gpu_manager.get_memory_stats()}")
        return model, tokenizer
    except ImportError:
        logger.warning("⚠️ bitsandbytes not installed, loading in FP16 (may use more memory)")
        try:
            # Fallback: Load in FP16 without quantization
            tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True,
                low_cpu_mem_usage=True
            )
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info(f"✅ Phi-3 loaded (FP16) on {device}")
            return model, tokenizer
        except Exception as e:
            logger.error(f"❌ Phi-3 load failed: {e}")
            return None, None
    except Exception as e:
        logger.error(f"❌ Phi-3 load failed: {e}")
        return None, None

# ========================================================
# DATA LOADING
# ========================================================

def load_excel_file(file, sheet_name=None):
    try:
        if sheet_name:
            df = pd.read_excel(file, sheet_name=sheet_name)
        else:
            df = pd.read_excel(file)
        
        df.columns = df.columns.str.strip()
        logger.info(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")
        return df
    except Exception as e:
        logger.error(f"❌ Load error: {e}")
        st.error(f"Error: {e}")
        return None

# ========================================================
# SEMANTIC MATCHING
# ========================================================

class SemanticMatcher:
    def __init__(self, embedding_model):
        self.embedding_model = embedding_model
        self.cache = {}
    
    def get_embedding(self, text: str):
        if pd.isna(text) or str(text).strip() == "":
            return None
        
        text_key = str(text).strip()
        if text_key in self.cache:
            return self.cache[text_key]
        
        with torch.no_grad():
            embedding = self.embedding_model.encode(
                text_key,
                convert_to_tensor=True,
                show_progress_bar=False
            )
        
        self.cache[text_key] = embedding
        return embedding
    
    def compute_similarity(self, text1: str, text2: str) -> float:
        emb1 = self.get_embedding(text1)
        emb2 = self.get_embedding(text2)
        
        if emb1 is None or emb2 is None:
            return 0.0
        
        return util.cos_sim(emb1, emb2).item()
    
    def batch_similarity(self, query_text: str, corpus_texts: List[str], top_k: int = 10):
        query_emb = self.get_embedding(query_text)
        if query_emb is None:
            return []
        
        corpus_embs = []
        valid_indices = []
        
        for idx, text in enumerate(corpus_texts):
            emb = self.get_embedding(text)
            if emb is not None:
                corpus_embs.append(emb)
                valid_indices.append(idx)
        
        if not corpus_embs:
            return []
        
        corpus_embs = torch.stack(corpus_embs)
        similarities = util.cos_sim(query_emb, corpus_embs)[0]
        top_results = torch.topk(similarities, k=min(top_k, len(similarities)))
        
        results = []
        for score, idx in zip(top_results.values.tolist(), top_results.indices.tolist()):
            results.append({
                'index': valid_indices[idx],
                'text': corpus_texts[valid_indices[idx]],
                'score': score
            })
        
        return results

# ========================================================
# INTERFACE-SQL MAPPING
# ========================================================

def generate_interface_sql_mapping(interface_df, sql_df, matcher, min_confidence=0.45):
    mappings = []
    
    with st.spinner("🔍 Analyzing interfaces and SQL..."):
        progress_bar = st.progress(0)
        
        for idx, interface_row in interface_df.iterrows():
            progress_bar.progress((idx + 1) / len(interface_df))
            
            interface_context = []
            for col in ['Application', 'Integration', 'Description', 'Source System', 'Target System']:
                if col in interface_row and pd.notna(interface_row[col]):
                    interface_context.append(str(interface_row[col]))
            
            interface_text = " ".join(interface_context)
            if not interface_text.strip():
                continue
            
            sql_corpus = []
            for _, sql_row in sql_df.iterrows():
                sql_context = [str(sql_row[col]) for col in sql_df.columns if pd.notna(sql_row[col])]
                sql_corpus.append(" ".join(sql_context))
            
            matches = matcher.batch_similarity(interface_text, sql_corpus, top_k=5)
            
            for match in matches:
                if match['score'] >= min_confidence:
                    sql_row = sql_df.iloc[match['index']]
                    
                    mapping = {
                        'Interface_Index': idx,
                        'SQL_Index': match['index'],
                        'Confidence_Score': match['score'],
                        'Application': interface_row.get('Application', ''),
                        'Integration': interface_row.get('Integration', ''),
                        'Source_System': interface_row.get('Source System', ''),
                        'Target_System': interface_row.get('Target System', ''),
                        'Flow_Direction': interface_row.get('Inbound/Outbound With Respect To Existing Acct Platform', ''),
                        'SQL_System': sql_row.get('system', sql_row.get('System', '')),
                        'SQL_File': sql_row.get('file', sql_row.get('File', '')),
                        'SQL_Query_Name': sql_row.get('queryname', sql_row.get('QueryName', ''))
                    }
                    
                    mappings.append(mapping)
        
        progress_bar.empty()
    
    if mappings:
        mapping_df = pd.DataFrame(mappings)
        return mapping_df.sort_values('Confidence_Score', ascending=False)
    return pd.DataFrame()

# ========================================================
# GRAPH VISUALIZATION
# ========================================================

def create_data_lineage_graph(interface_df, flow_col='Inbound/Outbound With Respect To Existing Acct Platform'):
    G = nx.DiGraph()
    
    colors = {
        'Inbound': '#667eea',
        'Outbound': '#f5576c',
        'Bidirectional': '#38ef7d',
        'Unknown': '#95a5a6'
    }
    
    edge_data = []
    node_data = {}
    
    for _, row in interface_df.iterrows():
        source = str(row.get('Source System', 'Unknown')).strip()
        target = str(row.get('Target System', 'Unknown')).strip()
        flow = str(row.get(flow_col, 'Unknown')).strip() if pd.notna(row.get(flow_col)) else 'Unknown'
        
        if pd.isna(row.get('Source System')) or pd.isna(row.get('Target System')):
            continue
        
        flow_normalized = 'Unknown'
        if 'inbound' in flow.lower():
            flow_normalized = 'Inbound'
        elif 'outbound' in flow.lower():
            flow_normalized = 'Outbound'
        elif 'bi' in flow.lower():
            flow_normalized = 'Bidirectional'
        
        for node in [source, target]:
            if node not in node_data:
                node_data[node] = {'size': 0, 'connections': set()}
            node_data[node]['size'] += 1
        
        node_data[source]['connections'].add(target)
        node_data[target]['connections'].add(source)
        
        edge_info = {
            'source': source,
            'target': target,
            'flow': flow_normalized,
            'color': colors[flow_normalized],
            'application': row.get('Application', ''),
            'integration': row.get('Integration', '')
        }
        edge_data.append(edge_info)
        
        G.add_edge(source, target, flow=flow_normalized, color=edge_info['color'])
    
    try:
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    except:
        pos = nx.random_layout(G, seed=42)
    
    edge_traces = []
    for flow_type, color in colors.items():
        edges = [e for e in edge_data if e['flow'] == flow_type]
        if not edges:
            continue
        
        edge_x, edge_y = [], []
        for edge in edges:
            x0, y0 = pos[edge['source']]
            x1, y1 = pos[edge['target']]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        
        edge_traces.append(go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=2, color=color),
            hoverinfo='none',
            mode='lines',
            name=flow_type,
            showlegend=True
        ))
    
    node_x, node_y, node_text, node_size, node_color = [], [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        
        size = node_data[node]['size']
        node_size.append(20 + size * 5)
        node_color.append(G.degree(node))
        
        connections = len(node_data[node]['connections'])
        node_text.append(f"{node}<br>Interfaces: {size}<br>Connections: {connections}")
    
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=[n.split()[-1] if len(n) > 15 else n for n in G.nodes()],
        textposition="top center",
        hovertext=node_text,
        marker=dict(
            showscale=True,
            colorscale='Viridis',
            size=node_size,
            color=node_color,
            line=dict(width=2, color='white'),
            colorbar=dict(title="Connections", thickness=15)
        ),
        showlegend=False
    )
    
    fig = go.Figure(
        data=edge_traces + [node_trace],
        layout=go.Layout(
            title='<b>Data Lineage Graph - Color-Coded by Flow Direction</b>',
            showlegend=True,
            hovermode='closest',
            margin=dict(b=20, l=5, r=5, t=60),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor='#f8f9fa',
            height=700,
            legend=dict(y=0.99, x=0.99, bgcolor="rgba(255,255,255,0.9)")
        )
    )
    
    return fig, G

# ========================================================
# PHI-3 INSIGHTS
# ========================================================

def generate_phi3_insights(llm_model, llm_tokenizer, interface_row, sql_info=None):
    if llm_model is None or llm_tokenizer is None:
        return generate_rule_based_insights(interface_row, sql_info)
    
    prompt_parts = ["Generate business insights for this integration:\n\n"]
    
    for col in ['Application', 'Integration', 'Description', 'Source System', 'Target System', 
                'Inbound/Outbound With Respect To Existing Acct Platform']:
        if col in interface_row and pd.notna(interface_row[col]):
            prompt_parts.append(f"{col}: {interface_row[col]}\n")
    
    if sql_info:
        prompt_parts.append(f"\nSQL Tables: {', '.join(sql_info.get('tables', []))}\n")
    
    prompt_parts.append("\nProvide:\n1. Business purpose\n2. Data flow\n3. Benefits\n4. Risks")
    prompt = "".join(prompt_parts)
    
    try:
        inputs = llm_tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(llm_model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = llm_model.generate(
                **inputs,
                max_new_tokens=500,
                temperature=0.7,
                top_p=0.9,
                do_sample=True,
                pad_token_id=llm_tokenizer.eos_token_id
            )
        
        response = llm_tokenizer.decode(outputs[0], skip_special_tokens=True)
        if prompt in response:
            response = response.replace(prompt, "").strip()
        
        return response
    except Exception as e:
        logger.error(f"Phi-3 error: {e}")
        return generate_rule_based_insights(interface_row, sql_info)

def generate_rule_based_insights(interface_row, sql_info=None):
    insights = ["**Business Purpose:**"]
    
    if 'Description' in interface_row and pd.notna(interface_row['Description']):
        insights.append(interface_row['Description'])
    else:
        insights.append(f"Data integration for {interface_row.get('Application', 'the system')}")
    
    insights.append("\n**Data Flow:**")
    source = interface_row.get('Source System', 'source')
    target = interface_row.get('Target System', 'target')
    flow = interface_row.get('Inbound/Outbound With Respect To Existing Acct Platform', '')
    
    if 'inbound' in str(flow).lower():
        insights.append(f"FROM {source} INTO account platform ({target})")
    elif 'outbound' in str(flow).lower():
        insights.append(f"FROM account platform TO {target}")
    else:
        insights.append(f"Between {source} and {target}")
    
    if sql_info and sql_info.get('tables'):
        insights.append(f"\n**Data Sources:** {len(sql_info['tables'])} tables")
    
    insights.append("\n**Benefits:**")
    insights.append("• Automated sync\n• Reduced errors\n• Data consistency")
    
    return "\n".join(insights)

# ========================================================
# MAIN APPLICATION
# ========================================================

def main():
    st.markdown(f"""
    <div class="premium-header">
        <h1 class="premium-title">🌐 Enterprise Data Explorer 360°</h1>
        <p class="premium-subtitle">GPU-Accelerated Semantic Matching & Data Lineage</p>
        <div>
            <span class="gpu-badge">🚀 Single GPU (8GB) Optimized</span>
            <span class="gpu-badge">🤖 Phi-3 4-bit Quantized</span>
            <span class="gpu-badge">⚡ MiniLM Embeddings</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.title("📁 Data Upload")
        
        st.subheader("1️⃣ Interface Document")
        interface_file = st.file_uploader("Interface Inventory", type=['xlsx', 'xls'], key='interface')
        if interface_file:
            with st.spinner("Loading..."):
                st.session_state.interface_df = load_excel_file(interface_file)
                if st.session_state.interface_df is not None:
                    st.success(f"✅ {len(st.session_state.interface_df)} interfaces")
        
        st.subheader("2️⃣ PMIM System (Optional)")
        pmim_file = st.file_uploader("PMIM Data", type=['xlsx', 'xls'], key='pmim')
        if pmim_file:
            st.session_state.pmim_df = load_excel_file(pmim_file, 'PMIMCurrentsystem')
        
        st.subheader("3️⃣ PB File Feeds (Optional)")
        pbfile_file = st.file_uploader("PB Feeds", type=['xlsx', 'xls'], key='pbfile')
        if pbfile_file:
            st.session_state.pbfile_df = load_excel_file(pbfile_file, 'PB File Feeds_ORIG')
        
        st.subheader("4️⃣ SQL Metadata (Optional)")
        sql_file = st.file_uploader("SQL Queries", type=['xlsx', 'xls'], key='sql')
        if sql_file:
            st.session_state.sql_df = load_excel_file(sql_file)
        
        st.markdown("---")
        st.subheader("🤖 AI Models")
        
        if st.button("🔄 Load Models", use_container_width=True):
            with st.spinner("Loading on GPU..."):
                st.session_state.embedding_model = load_embedding_model()
                llm, tok = load_llm_model()
                st.session_state.llm_model = llm
                st.session_state.llm_tokenizer = tok
        
        if st.session_state.embedding_model:
            st.info("🟢 Embeddings: Ready")
        else:
            st.warning("🔴 Embeddings: Not loaded")
        
        if st.session_state.llm_model:
            st.info("🟢 Phi-3 LLM: Ready (4-bit)")
        else:
            st.warning("🔴 Phi-3 LLM: Not loaded")
        
        # Memory stats
        if torch.cuda.is_available():
            st.caption(f"📊 {gpu_manager.get_memory_stats()}")
            
            if st.button("🧹 Clear GPU Memory", use_container_width=True):
                gpu_manager.clear_memory()
                st.success("✅ Memory cleared")
                st.rerun()
        
        st.markdown("---")
        
        if st.session_state.interface_df is not None and st.session_state.embedding_model:
            st.subheader("🔗 Semantic Matching")
            
            min_conf = st.slider("Min Confidence", 0.3, 0.9, 0.45, 0.05)
            
            if st.session_state.sql_df is not None:
                if st.button("⚡ Run Matching", use_container_width=True):
                    matcher = SemanticMatcher(st.session_state.embedding_model)
                    
                    start = time.time()
                    st.session_state.mapping_df = generate_interface_sql_mapping(
                        st.session_state.interface_df,
                        st.session_state.sql_df,
                        matcher,
                        min_conf
                    )
                    
                    if not st.session_state.mapping_df.empty:
                        st.success(f"✅ {len(st.session_state.mapping_df)} matches in {time.time()-start:.2f}s")
        
        st.markdown("---")
        
        if st.session_state.interface_df is not None:
            st.subheader("🔍 Filters")
            
            col_name = 'Inbound/Outbound With Respect To Existing Acct Platform'
            if col_name in st.session_state.interface_df.columns:
                vals = st.session_state.interface_df[col_name].dropna().unique()
                st.session_state.filter_flow_direction = st.multiselect(
                    "Flow Direction",
                    sorted(vals),
                    st.session_state.filter_flow_direction
                )
            
            if 'Application' in st.session_state.interface_df.columns:
                apps = st.session_state.interface_df['Application'].dropna().unique()
                st.session_state.filter_application = st.multiselect(
                    "Application",
                    sorted(apps),
                    st.session_state.filter_application
                )
    
    # Main content
    if st.session_state.interface_df is None:
        st.info("👈 Upload Interface Document to begin")
    else:
        df = st.session_state.interface_df.copy()
        
        # Apply filters
        if st.session_state.filter_flow_direction:
            df = df[df['Inbound/Outbound With Respect To Existing Acct Platform'].isin(st.session_state.filter_flow_direction)]
        
        if st.session_state.filter_application:
            df = df[df['Application'].isin(st.session_state.filter_application)]
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Interfaces</div><div class="metric-value">{len(df)}</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Sources</div><div class="metric-value">{df["Source System"].nunique() if "Source System" in df.columns else 0}</div></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Targets</div><div class="metric-value">{df["Target System"].nunique() if "Target System" in df.columns else 0}</div></div>', unsafe_allow_html=True)
        with col4:
            mappings = len(st.session_state.mapping_df) if st.session_state.mapping_df is not None else 0
            st.markdown(f'<div class="metric-card"><div class="metric-label">Mappings</div><div class="metric-value">{mappings}</div></div>', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Tabs
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🌐 Lineage Graph", "🔗 Mappings", "🤖 AI Insights"])
        
        with tab1:
            st.subheader("📊 Overview Dashboard")
            
            col_name = 'Inbound/Outbound With Respect To Existing Acct Platform'
            if col_name in df.columns:
                st.markdown("### Flow Direction Distribution")
                
                counts = df[col_name].value_counts()
                colors_list = ['#667eea' if 'inbound' in str(x).lower() else '#f5576c' if 'outbound' in str(x).lower() else '#38ef7d' for x in counts.index]
                
                fig = go.Figure(go.Bar(x=counts.index, y=counts.values, marker_color=colors_list, text=counts.values, textposition='auto'))
                fig.update_layout(title="By Flow Direction", height=400)
                st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.subheader("🌐 Data Lineage Graph")
            
            st.markdown("""
            <div class="ai-insight" style="background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border-left-color: #2196f3;">
                <strong>Legend:</strong><br>
                <span class="flow-inbound">● Inbound</span> - INTO platform<br>
                <span class="flow-outbound">● Outbound</span> - OUT OF platform<br>
                <span class="flow-bidirectional">● Bidirectional</span> - Two-way
            </div>
            """, unsafe_allow_html=True)
            
            if len(df) > 0:
                with st.spinner("Creating graph..."):
                    fig, G = create_data_lineage_graph(df)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Nodes", G.number_of_nodes())
                    col2.metric("Edges", G.number_of_edges())
                    col3.metric("Avg Degree", f"{sum(dict(G.degree()).values()) / G.number_of_nodes():.1f}")
                    col4.metric("Components", nx.number_weakly_connected_components(G))
        
        with tab3:
            st.subheader("🔗 Interface-SQL Mappings")
            
            if st.session_state.mapping_df is not None and not st.session_state.mapping_df.empty:
                st.success(f"✅ {len(st.session_state.mapping_df)} mappings found")
                
                st.dataframe(st.session_state.mapping_df, use_container_width=True, height=400)
                
                csv = st.session_state.mapping_df.to_csv(index=False)
                st.download_button("📥 Download CSV", csv, f"mappings_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
            else:
                st.info("Run semantic matching to generate mappings")
        
        with tab4:
            st.subheader("🤖 AI Insights")
            
            if st.session_state.llm_model:
                st.success("✨ Phi-3 Active")
            
            options = [f"{row.get('Integration', 'N/A')} - {row.get('Application', 'N/A')}" for _, row in df.iterrows()]
            
            if options:
                selected = st.selectbox("Select Interface", options)
                selected_idx = df.index[df.apply(lambda r: f"{r.get('Integration', 'N/A')} - {r.get('Application', 'N/A')}" == selected, axis=1)].tolist()[0]
                selected_row = df.loc[selected_idx]
                
                if st.button("🚀 Generate Insights", type="primary"):
                    with st.spinner("Generating..."):
                        insights = generate_phi3_insights(
                            st.session_state.llm_model,
                            st.session_state.llm_tokenizer,
                            selected_row
                        )
                        
                        st.markdown(f'<div class="ai-insight">{insights}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
