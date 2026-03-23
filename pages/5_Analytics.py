import streamlit as st
import sys
import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import get_analytics_data, get_all_candidates, get_activity_log

st.set_page_config(page_title="Analytics — Anilee Hiring", page_icon="📈", layout="wide")
st.title("📈 Analytics & Reports")

data = get_analytics_data()
all_candidates = get_all_candidates()

# ── TOP METRICS ───────────────────────────────────────────────────────────────
total = len(all_candidates)
hired = sum(1 for c in all_candidates if c["stage"] == "Hired")
hot = sum(1 for c in all_candidates if c.get("score_band") == "Hot 🔥")
screened = sum(1 for c in all_candidates if c.get("score", 0) > 0)
rejected = sum(1 for c in all_candidates if c["stage"] == "Rejected")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Candidates", total)
m2.metric("Screened by AI", screened)
m3.metric("🔥 Hot Leads", hot)
m4.metric("Hired", hired)
m5.metric("Conversion Rate", f"{int(hired/max(total,1)*100)}%")

st.divider()

# ── CHARTS ROW 1 ──────────────────────────────────────────────────────────────
c1, c2 = st.columns(2)

with c1:
    st.subheader("Pipeline Funnel")
    stage_order = ["New", "Outreached", "Screening", "Screened", "Interview Scheduled", "Hired"]
    stage_counts = [data["stage_dist"].get(s, 0) for s in stage_order]
    stage_colors = ["#6C757D", "#0D6EFD", "#FFC107", "#0DCAF0", "#FF6B35", "#198754"]

    fig_funnel = go.Figure(go.Funnel(
        y=stage_order,
        x=stage_counts,
        textinfo="value+percent initial",
        marker=dict(color=stage_colors),
        connector=dict(line=dict(color="royalblue", dash="dot", width=2))
    ))
    fig_funnel.update_layout(
        margin=dict(l=0, r=0, t=10, b=0), height=360,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig_funnel, use_container_width=True)

with c2:
    st.subheader("Candidate Sources")
    source_data = data.get("source_dist", {})
    if source_data:
        fig_pie = px.pie(
            names=list(source_data.keys()),
            values=list(source_data.values()),
            color_discrete_sequence=px.colors.qualitative.Set2,
            hole=0.35
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(
            margin=dict(l=0, r=0, t=10, b=0), height=360,
            showlegend=True,
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No source data yet.")

# ── CHARTS ROW 2 ──────────────────────────────────────────────────────────────
c3, c4 = st.columns(2)

with c3:
    st.subheader("Score Band Distribution")
    score_data = data.get("score_dist", {})
    if score_data:
        band_order = ["Hot 🔥", "Warm ✅", "Cold ❄️", "Rejected ❌"]
        band_colors_hex = {"Hot 🔥": "#DC3545", "Warm ✅": "#198754",
                           "Cold ❄️": "#0D6EFD", "Rejected ❌": "#6C757D"}
        names = [b for b in band_order if b in score_data]
        values = [score_data[b] for b in names]
        colors = [band_colors_hex[b] for b in names]

        fig_bar = go.Figure(go.Bar(
            x=names, y=values, marker_color=colors,
            text=values, textposition="auto", textfont=dict(size=14)
        ))
        fig_bar.update_layout(
            margin=dict(l=0, r=0, t=10, b=0), height=300,
            showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="#eee")
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No candidates scored yet.")

with c4:
    st.subheader("Stage Breakdown")
    stage_data = data.get("stage_dist", {})
    if stage_data:
        scolors = {
            "New": "#6C757D", "Outreached": "#0D6EFD", "Screening": "#FFC107",
            "Screened": "#0DCAF0", "Interview Scheduled": "#FF6B35",
            "Hired": "#198754", "Rejected": "#DC3545"
        }
        names2 = list(stage_data.keys())
        values2 = list(stage_data.values())
        colors2 = [scolors.get(n, "#999") for n in names2]

        fig_bar2 = go.Figure(go.Bar(
            x=names2, y=values2, marker_color=colors2,
            text=values2, textposition="auto", textfont=dict(size=13)
        ))
        fig_bar2.update_layout(
            margin=dict(l=0, r=0, t=10, b=0), height=300,
            showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(tickangle=-20), yaxis=dict(gridcolor="#eee")
        )
        st.plotly_chart(fig_bar2, use_container_width=True)
    else:
        st.info("No stage data yet.")

st.divider()

# ── CANDIDATE TABLE ───────────────────────────────────────────────────────────
st.subheader("All Candidates — Full Table")

if all_candidates:
    df = pd.DataFrame(all_candidates)
    display_cols = ["id", "name", "phone", "source", "stage", "score", "score_band",
                    "experience_months", "expected_salary", "location", "created_at"]
    available = [col for col in display_cols if col in df.columns]
    df_display = df[available].copy()
    df_display.columns = [c.replace("_", " ").title() for c in df_display.columns]
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.download_button(
        "📥 Export to CSV",
        df.to_csv(index=False),
        "candidates_export.csv",
        "text/csv",
        use_container_width=False
    )
else:
    st.info("No candidates yet.")

st.divider()

# ── ACTIVITY LOG ─────────────────────────────────────────────────────────────
st.subheader("📋 Activity Log")
activity = get_activity_log(limit=100)
if activity:
    df_act = pd.DataFrame(activity)
    df_act = df_act[["created_at", "candidate_name", "action", "details", "performed_by"]]
    df_act.columns = ["Timestamp", "Candidate", "Action", "Details", "By"]
    st.dataframe(df_act, use_container_width=True, hide_index=True)
else:
    st.info("No activity recorded yet.")
