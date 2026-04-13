import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from matcher import load_data, match_jobs

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IT Jobs PH",
    layout="wide",
)

# Theme Configuration and Toggle State
current_is_dark = False
if os.path.exists(".streamlit/config.toml"):
    with open(".streamlit/config.toml", "r", encoding="utf-8") as f:
        current_is_dark = 'base="dark"' in f.read()

# Dynamic card colors for theme sync
card_bg = "#1f2937" if current_is_dark else "#ffffff"
border_col = "#374151" if current_is_dark else "#e5e7eb"

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    .block-container {{ padding-top: 2rem; padding-bottom: 2rem; }}
    [data-testid="metric-container"] {{
        background-color: {card_bg};
        border: 1px solid {border_col};
        border-radius: 6px;
        padding: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }}
    .match-card {{
        background-color: {card_bg};
        border: 1px solid {border_col};
        border-radius: 6px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }}
    .score-badge {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: 500;
        font-size: 0.85rem;
    }}
    .score-high   {{ background: #def7ec; color: #046c4e; }}
    .score-medium {{ background: #fdf6b2; color: #723b13; }}
    .score-low    {{ background: #fde8e8; color: #9b1c1c; }}
    h1, h2, h3 {{ font-family: "Inter", sans-serif; font-weight: 600; color: inherit; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 2rem; }}
    .stTabs [data-baseweb="tab"] {{ height: 3rem; white-space: pre; background-color: transparent; }}
</style>
""", unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def get_data():
    return load_data("itjob_header_cleaned.csv")

df = get_data()

# ── Header ───────────────────────────────────────────────────────────────────
col_title, col_toggle = st.columns([6, 1])
with col_title:
    st.title("IT Jobs PH")
    st.caption("525 listings · Philippines | Built with Streamlit · scikit-learn · Plotly")
with col_toggle:
    st.write("") # Spacer for vertical alignment
    theme_toggle = st.toggle("Dark Mode", value=current_is_dark)

if theme_toggle != current_is_dark:
    os.makedirs(".streamlit", exist_ok=True)
    if theme_toggle:
        config_content = '''[theme]
base="dark"
primaryColor="#3b82f6"
'''
    else:
        config_content = '''[theme]
base="light"
primaryColor="#2563eb"
backgroundColor="#f9fafb"
secondaryBackgroundColor="#f3f4f6"
textColor="#374151"
'''
    with open(".streamlit/config.toml", "w", encoding="utf-8") as f:
        f.write(config_content)
    import time
    time.sleep(0.3)
    st.rerun()

# ── Global filters ─────────────────────────────────────────────────────────────
with st.expander("Global Filters", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    
    all_levels = sorted(df["level"].dropna().unique().tolist())
    with col1:
        selected_levels = st.multiselect("Experience level", options=all_levels, default=all_levels)

    all_modes = sorted(df["mode"].dropna().unique().tolist())
    with col2:
        selected_modes = st.multiselect("Work mode", options=all_modes, default=all_modes)

    all_types = sorted(df["type"].dropna().unique().tolist())
    with col3:
        selected_types = st.multiselect("Job type", options=all_types, default=["Full Time"])

    sal_min_data = int(df["salary_from"].min())
    sal_max_data = int(df["salary_to"].max())
    with col4:
        salary_range = st.slider("Salary range (PHP/month)", min_value=0, max_value=500_000, value=(20_000, 200_000), step=5_000, format="PHP %d")

# Apply global filters
filtered_df = df.copy()
if selected_levels:
    filtered_df = filtered_df[filtered_df["level"].isin(selected_levels)]
if selected_modes:
    filtered_df = filtered_df[filtered_df["mode"].isin(selected_modes)]
if selected_types:
    filtered_df = filtered_df[filtered_df["type"].isin(selected_types)]

filtered_df = filtered_df[
    (filtered_df["salary_mid"] >= salary_range[0]) &
    (filtered_df["salary_mid"] <= salary_range[1])
]

# ── Tabs Navigation ───────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["Dashboard", "Job Matcher"])

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("IT Job Market Overview")
    st.caption(f"Showing {len(filtered_df):,} of {len(df):,} listings based on your filters")
    
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a: st.metric("Total listings", f"{len(filtered_df):,}")
    with col_b: st.metric("Median salary", f"PHP {filtered_df['salary_mid'].median():,.0f}/mo")
    with col_c:
        remote_pct = (filtered_df["mode"].isin(["Remote", "Hybrid"]).sum() / max(len(filtered_df), 1) * 100)
        st.metric("Remote / hybrid", f"{remote_pct:.0f}%")
    with col_d:
        top_spec = filtered_df["tech_specialisation"].value_counts().index[0] if len(filtered_df) > 0 else "-"
        st.metric("Top specialisation", top_spec)

    st.divider()

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("**Salary range by experience level**")
        level_order = ["Junior", "Middle", "Senior", "Lead"]
        fig_box = px.box(
            filtered_df[filtered_df["level"].isin(level_order)],
            x="level", y="salary_mid", category_orders={"level": level_order}, color="level",
            color_discrete_sequence=["#2563eb", "#059669", "#d97706", "#7c3aed"],
            labels={"salary_mid": "Monthly salary (PHP)", "level": "Level"}, points="outliers"
        )
        fig_box.update_layout(showlegend=False, yaxis_tickformat=",.0f", margin=dict(t=20, b=20, l=10, r=10))
        st.plotly_chart(fig_box, use_container_width=True)

    with col_right:
        st.markdown("**Work mode**")
        mode_counts = filtered_df["mode"].value_counts().reset_index()
        mode_counts.columns = ["mode", "count"]
        fig_donut = px.pie(mode_counts, names="mode", values="count", hole=0.55, color_discrete_sequence=["#2563eb", "#059669", "#d97706"])
        fig_donut.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.2), margin=dict(t=20, b=40, l=10, r=10))
        fig_donut.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_donut, use_container_width=True)

    col_left2, col_right2 = st.columns([2, 3])

    with col_left2:
        st.markdown("**Top 15 specialisations**")
        top_specs = filtered_df["tech_specialisation"].value_counts().head(15).reset_index()
        top_specs.columns = ["specialisation", "count"]
        fig_bar = px.bar(top_specs, x="count", y="specialisation", orientation="h", color="count", color_continuous_scale="Blues", labels={"count": "Listings", "specialisation": ""})
        fig_bar.update_layout(showlegend=False, coloraxis_showscale=False, yaxis=dict(autorange="reversed"), margin=dict(t=20, b=20, l=10, r=10))
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_right2:
        st.markdown("**Experience required by level**")
        fig_violin = px.violin(
            filtered_df[filtered_df["level"].isin(level_order)],
            x="level", y="work_experience_years", category_orders={"level": level_order}, color="level",
            color_discrete_sequence=["#2563eb", "#059669", "#d97706", "#7c3aed"], box=True, points="outliers",
            labels={"work_experience_years": "Years required", "level": "Level"}
        )
        fig_violin.update_layout(showlegend=False, margin=dict(t=20, b=20, l=10, r=10))
        st.plotly_chart(fig_violin, use_container_width=True)

    st.markdown("**Education requirements**")
    edu_counts = filtered_df["education_level"].value_counts().reset_index()
    edu_counts.columns = ["education", "count"]
    fig_edu = px.bar(edu_counts, x="education", y="count", color="education", color_discrete_sequence=px.colors.qualitative.Pastel, labels={"count": "Listings", "education": "Education level"})
    fig_edu.update_layout(showlegend=False, margin=dict(t=20, b=20, l=10, r=10))
    st.plotly_chart(fig_edu, use_container_width=True)

    with st.expander("View raw data", expanded=False):
        st.dataframe(filtered_df[["tech_specialisation", "level", "mode", "type", "salary_from", "salary_to", "work_experience_years", "education_level"]], use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — JOB MATCHER
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Job Matcher")
    st.caption("Rank jobs based on your profile.")
    
    with st.form("matcher_form"):
        col1, col2 = st.columns(2)
        with col1:
            user_skills = st.text_input("Skills / keywords", placeholder="e.g. Python, data analysis, SQL")
            user_level = st.selectbox("Your experience level", options=["Any"] + all_levels)
            user_mode = st.selectbox("Preferred work mode", options=["Any"] + all_modes)
            user_type = st.selectbox("Job type preference", options=["Any"] + all_types)
        
        with col2:
            user_exp = st.slider("Years of experience", min_value=0.0, max_value=15.0, value=3.0, step=0.5, format="%.1f yrs")
            user_salary_min = st.number_input("Min salary expectation (PHP/month)", min_value=0, max_value=500_000, value=40_000, step=5_000)
            user_salary_max = st.number_input("Max salary expectation (PHP/month)", min_value=0, max_value=500_000, value=120_000, step=5_000)
            top_n = st.slider("Number of results to show", min_value=3, max_value=20, value=8)

        submitted = st.form_submit_button("Find Matches", use_container_width=True)

    if submitted:
        level_filter = [] if user_level == "Any" else [user_level]
        mode_filter  = [] if user_mode  == "Any" else [user_mode]
        type_filter  = [] if user_type  == "Any" else [user_type]

        with st.spinner("Running matching engine..."):
            results = match_jobs(
                df=df, skill_query=user_skills, level=level_filter, mode=mode_filter, job_type=type_filter,
                exp_years=user_exp, salary_min=user_salary_min, salary_max=user_salary_max, top_n=top_n
            )

        if results.empty:
            st.warning("No jobs matched your criteria. Try adjusting your filters.")
        else:
            st.success(f"Successfully matched {len(results)} jobs.")
            
            st.markdown("**Match Score Breakdown**")
            fig_scores = px.bar(results, x="match_pct", y=results.index.astype(str) + ". " + results["tech_specialisation"] + " (" + results["level"] + ")", orientation="h", color="match_pct", color_continuous_scale=["#f87171", "#fbbf24", "#34d399"], range_color=[0, 100], labels={"match_pct": "Match %", "y": ""}, text="match_pct")
            fig_scores.update_traces(texttemplate="%{text}%", textposition="outside")
            fig_scores.update_layout(coloraxis_showscale=False, yaxis=dict(autorange="reversed"), xaxis=dict(range=[0, 115]), margin=dict(t=20, b=20, l=10, r=10), height=max(300, len(results) * 42))
            st.plotly_chart(fig_scores, use_container_width=True)

            st.markdown("**Score Analysis**")
            results_long = results.copy()
            results_long["label"] = results_long["tech_specialisation"] + " (" + results_long["level"] + ")"
            fig_stacked = go.Figure()
            fig_stacked.add_trace(go.Bar(name="Skill match (max 60)", y=results_long["label"], x=results_long["skill_score"].round(1), orientation="h", marker_color="#3b82f6"))
            fig_stacked.add_trace(go.Bar(name="Salary fit (max 25)", y=results_long["label"], x=results_long["salary_score"].round(1), orientation="h", marker_color="#10b981"))
            fig_stacked.add_trace(go.Bar(name="Experience fit (max 15)", y=results_long["label"], x=results_long["exp_score"].round(1), orientation="h", marker_color="#f59e0b"))
            fig_stacked.update_layout(barmode="stack", legend=dict(orientation="h", yanchor="bottom", y=1.02), yaxis=dict(autorange="reversed"), xaxis=dict(title="Score breakdown", range=[0, 100]), margin=dict(t=60, b=20, l=10, r=10), height=max(300, len(results) * 42))
            st.plotly_chart(fig_stacked, use_container_width=True)

            st.markdown("**Matched Job Listings**")
            for _, row in results.iterrows():
                score = int(row["match_pct"])
                badge_class = "score-high" if score >= 70 else "score-medium" if score >= 45 else "score-low"
                
                exp_req = f"{row['work_experience_years']:.0f} yrs" if pd.notna(row['work_experience_years']) else "Not specified"
                
                st.markdown(f"""
                <div class="match-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                        <strong style="font-size:1.05rem; color: inherit;">{row['tech_specialisation']}</strong>
                        <span class="score-badge {badge_class}">{score}% Match</span>
                    </div>
                    <div style="display:flex; gap:20px; flex-wrap:wrap; font-size:0.85rem; color: inherit;">
                        <span><strong>Level:</strong> {row['level']}</span>
                        <span><strong>Mode:</strong> {row['mode']}</span>
                        <span><strong>Type:</strong> {row['type']}</span>
                        <span><strong>Salary:</strong> PHP {row['salary_from']:,.0f} - {row['salary_to']:,.0f}/mo</span>
                        <span><strong>Education:</strong> {row['education_level']}</span>
                        <span><strong>Exp Required:</strong> {exp_req}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.divider()
            csv_out = results.drop(columns=["skill_score","salary_score","exp_score"]).to_csv(index=False)
            st.download_button("Download Results (CSV)", data=csv_out, file_name="matched_jobs.csv", mime="text/csv")
