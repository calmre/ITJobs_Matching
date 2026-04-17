import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from matcher import load_data, match_jobs, build_clusters
from auth import require_auth, logout
from chatbot import render_chat

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IT Jobs PH",
    layout="wide",
)

# ── Auth & Role ───────────────────────────────────────────────────────────────
role = require_auth()

# ── Theme ─────────────────────────────────────────────────────────────────────
current_is_dark = False
if os.path.exists(".streamlit/config.toml"):
    with open(".streamlit/config.toml", "r", encoding="utf-8") as f:
        current_is_dark = 'base="dark"' in f.read()

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
    .stTabs [data-baseweb="tab-list"] {{ gap: 2.5rem; }}
    .stTabs [data-baseweb="tab"] {{ height: 3.5rem; font-size: 1.1rem; font-weight: 600; background-color: transparent; }}
    [data-testid="stChatInput"] textarea {{ font-size: 0.95rem; }}
</style>
""", unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def get_data():
    return load_data("itjob_header_cleaned.csv")

@st.cache_data
def get_clustered_data():
    """
    Build K-Means + hierarchical clusters once and cache the result.
    This also trains the global _KMEANS_MODEL used by match_jobs() for the
    cluster boost — so we call it at startup, not lazily.
    """
    raw = load_data("itjob_header_cleaned.csv")
    return build_clusters(raw, n_clusters=8)

df = get_data()
clustered_df = get_clustered_data()  # trains models as a side-effect

# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_toggle, col_role, col_logout = st.columns([5, 1, 1, 1])

with col_title:
    st.title("IT Jobs PH")
    st.caption("525 listings · Philippines | Built with Streamlit · scikit-learn · Plotly · Claude AI")

with col_toggle:
    st.write("")
    theme_toggle = st.toggle("Dark Mode", value=current_is_dark)

with col_role:
    st.write("")
    if role == "admin":
        full_name = st.session_state.get("username", "Admin")
        st.success(f" {full_name}")
    elif role == "user":
        full_name = st.session_state.get("username", "User")
        st.info(f" {full_name}")
    else:
        st.info(" Guest")

with col_logout:
    st.write("")
    if role == "guest":
        if st.button("Log in", use_container_width=True):
            logout()
    else:
        if st.button("Log out", use_container_width=True):
            logout()

# Separator for the header
st.divider()

# ── Theme toggle handler ───────────────────────────────────────────────────────
if theme_toggle != current_is_dark:
    os.makedirs(".streamlit", exist_ok=True)
    config_content = (
        '[theme]\nbase="dark"\nprimaryColor="#3b82f6"\n'
        if theme_toggle else
        '[theme]\nbase="light"\nprimaryColor="#2563eb"\nbackgroundColor="#f9fafb"\nsecondaryBackgroundColor="#f3f4f6"\ntextColor="#374151"\n'
    )
    with open(".streamlit/config.toml", "w", encoding="utf-8") as f:
        f.write(config_content)
    import time; time.sleep(0.3)
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

    with col4:
        salary_range = st.slider("Salary range (PHP/month)", min_value=0, max_value=500_000,
                                  value=(20_000, 200_000), step=5_000, format="PHP %d")

# Apply filters
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

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_labels = [" Dashboard", " Job Matcher", "AI Chatbot"]
if role == "admin":
    tab_labels.append(" Admin Panel")

tabs = st.tabs(tab_labels)
tab_dashboard = tabs[0]
tab_matcher   = tabs[1]
tab_chat      = tabs[2]
tab_admin     = tabs[3] if role == "admin" else None


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_dashboard:
    st.subheader("IT Job Market Overview")
    st.caption(f"Showing {len(filtered_df):,} of {len(df):,} listings based on your filters")

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a: st.metric("Total listings", f"{len(filtered_df):,}")
    with col_b: st.metric("Median salary", f"PHP {filtered_df['salary_mid'].median():,.0f}/mo")
    with col_c:
        remote_pct = filtered_df["mode"].isin(["Remote", "Hybrid"]).sum() / max(len(filtered_df), 1) * 100
        st.metric("Remote / hybrid", f"{remote_pct:.0f}%")
    with col_d:
        top_spec = filtered_df["tech_specialisation"].value_counts().index[0] if len(filtered_df) > 0 else "-"
        st.metric("Top specialisation", top_spec)

    st.divider()
    level_order = ["Junior", "Middle", "Senior", "Lead"]

    col_left, col_right = st.columns([3, 2])
    with col_left:
        st.markdown("**Salary range by experience level**")
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
        fig_donut = px.pie(mode_counts, names="mode", values="count", hole=0.55,
                           color_discrete_sequence=["#2563eb", "#059669", "#d97706"])
        fig_donut.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                                 margin=dict(t=20, b=40, l=10, r=10))
        fig_donut.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_donut, use_container_width=True)

    col_left2, col_right2 = st.columns([2, 3])
    with col_left2:
        st.markdown("**Top 15 specialisations**")
        top_specs = filtered_df["tech_specialisation"].value_counts().head(15).reset_index()
        top_specs.columns = ["specialisation", "count"]
        fig_bar = px.bar(top_specs, x="count", y="specialisation", orientation="h", color="count",
                         color_continuous_scale="Blues", labels={"count": "Listings", "specialisation": ""})
        fig_bar.update_layout(showlegend=False, coloraxis_showscale=False,
                              yaxis=dict(autorange="reversed"), margin=dict(t=20, b=20, l=10, r=10))
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_right2:
        st.markdown("**Experience required by level**")
        fig_violin = px.violin(
            filtered_df[filtered_df["level"].isin(level_order)],
            x="level", y="work_experience_years", category_orders={"level": level_order}, color="level",
            color_discrete_sequence=["#2563eb", "#059669", "#d97706", "#7c3aed"],
            box=True, points="outliers",
            labels={"work_experience_years": "Years required", "level": "Level"}
        )
        fig_violin.update_layout(showlegend=False, margin=dict(t=20, b=20, l=10, r=10))
        st.plotly_chart(fig_violin, use_container_width=True)

    st.markdown("**Education requirements**")
    edu_counts = filtered_df["education_level"].value_counts().reset_index()
    edu_counts.columns = ["education", "count"]
    fig_edu = px.bar(edu_counts, x="education", y="count", color="education",
                     color_discrete_sequence=px.colors.qualitative.Pastel,
                     labels={"count": "Listings", "education": "Education level"})
    fig_edu.update_layout(showlegend=False, margin=dict(t=20, b=20, l=10, r=10))
    st.plotly_chart(fig_edu, use_container_width=True)

    with st.expander("View raw data", expanded=False):
        st.dataframe(
            filtered_df[["tech_specialisation", "level", "mode", "type",
                          "salary_from", "salary_to", "work_experience_years", "education_level"]],
            use_container_width=True, hide_index=True
        )

    # ── Clustering section ────────────────────────────────────────────────────
    st.divider()
    st.subheader("Job Market Clusters")
    st.caption(
        "Jobs grouped by skill similarity, salary band, and experience level using "
        "K-Means (8 clusters) and Hierarchical (Ward linkage) clustering."
    )

    cluster_tab1, cluster_tab2 = st.tabs(["K-Means Clusters", "Hierarchical Clusters"])

    with cluster_tab1:
        st.markdown("**K-Means cluster map** — each dot is a job, coloured by cluster")
        st.caption(
            "Axes are PCA components (compressed from ~300 TF-IDF dimensions to 2D). "
            "Cluster names are the top TF-IDF terms at each centroid."
        )

        # Merge cluster info onto filtered_df using index alignment
        plot_df = filtered_df.copy()
        plot_df = plot_df.merge(
            clustered_df[["jobid", "kmeans_cluster", "kmeans_label", "pca_x", "pca_y"]],
            on="jobid", how="left"
        ).dropna(subset=["pca_x", "pca_y"])

        if not plot_df.empty:
            fig_scatter = px.scatter(
                plot_df,
                x="pca_x", y="pca_y",
                color="kmeans_label",
                hover_data={
                    "tech_specialisation": True,
                    "level": True,
                    "salary_mid": ":,.0f",
                    "pca_x": False,
                    "pca_y": False,
                },
                labels={"pca_x": "PCA Component 1", "pca_y": "PCA Component 2", "kmeans_label": "Cluster"},
                color_discrete_sequence=px.colors.qualitative.Bold,
                opacity=0.75,
            )
            fig_scatter.update_traces(marker=dict(size=6))
            fig_scatter.update_layout(
                legend=dict(orientation="v", x=1.01, y=1),
                margin=dict(t=20, b=20, l=10, r=10),
                height=500,
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

            # Cluster summary table
            st.markdown("**Cluster summary**")
            cluster_summary = (
                plot_df.groupby("kmeans_label")
                .agg(
                    Jobs=("jobid", "count"),
                    Median_Salary=("salary_mid", "median"),
                    Avg_Exp=("work_experience_years", "mean"),
                )
                .rename(columns={"Median_Salary": "Median Salary (PHP)", "Avg_Exp": "Avg Exp (yrs)"})
                .sort_values("Jobs", ascending=False)
                .reset_index()
                .rename(columns={"kmeans_label": "Cluster"})
            )
            cluster_summary["Median Salary (PHP)"] = cluster_summary["Median Salary (PHP)"].map("PHP {:,.0f}".format)
            cluster_summary["Avg Exp (yrs)"] = cluster_summary["Avg Exp (yrs)"].map("{:.1f}".format)
            st.dataframe(cluster_summary, use_container_width=True, hide_index=True)
        else:
            st.info("No cluster data available for the current filter selection.")

    with cluster_tab2:
        st.markdown("**Hierarchical cluster map** — same PCA layout, coloured by Ward linkage cluster")
        st.caption(
            "Ward linkage merges the pair of clusters that minimises the increase in total "
            "within-cluster variance at each step. Cut at 8 clusters."
        )

        plot_df2 = filtered_df.copy()
        plot_df2 = plot_df2.merge(
            clustered_df[["jobid", "hier_cluster", "pca_x", "pca_y"]],
            on="jobid", how="left"
        ).dropna(subset=["pca_x", "pca_y"])

        if not plot_df2.empty:
            plot_df2["hier_cluster"] = "Cluster " + plot_df2["hier_cluster"].astype(int).astype(str)

            fig_hier = px.scatter(
                plot_df2,
                x="pca_x", y="pca_y",
                color="hier_cluster",
                hover_data={
                    "tech_specialisation": True,
                    "level": True,
                    "salary_mid": ":,.0f",
                    "pca_x": False,
                    "pca_y": False,
                },
                labels={"pca_x": "PCA Component 1", "pca_y": "PCA Component 2", "hier_cluster": "Hier. Cluster"},
                color_discrete_sequence=px.colors.qualitative.Pastel,
                opacity=0.75,
            )
            fig_hier.update_traces(marker=dict(size=6))
            fig_hier.update_layout(
                legend=dict(orientation="v", x=1.01, y=1),
                margin=dict(t=20, b=20, l=10, r=10),
                height=500,
            )
            st.plotly_chart(fig_hier, use_container_width=True)

            # Dendrogram (sampled — full 525-node dendrogram is unreadable)
            st.markdown("**Dendrogram** — top 30 merges (Ward linkage)")
            st.caption(
                "Each horizontal line is a merge event. Height = distance cost of that merge. "
                "Taller bars = more dissimilar groups being joined."
            )

            link_matrix = clustered_df.attrs.get("linkage_matrix")
            if link_matrix is not None:
                import plotly.figure_factory as ff
                # Show only the last 30 merges (top of the tree) to keep it readable
                n = len(link_matrix)
                last_n = 30
                truncated = link_matrix[n - last_n:]

                # Re-label leaf nodes as integers for ff.create_dendrogram compatibility
                labels = [str(i) for i in range(last_n + 1)]
                try:
                    fig_dendro = ff.create_dendrogram(
                        truncated[:, :2],   # only the merge-pair columns
                        orientation="bottom",
                        labels=labels,
                        color_threshold=truncated[:, 2].mean(),
                    )
                    fig_dendro.update_layout(
                        xaxis=dict(showticklabels=False),
                        yaxis=dict(title="Merge distance (Ward)"),
                        margin=dict(t=20, b=20, l=40, r=10),
                        height=350,
                    )
                    st.plotly_chart(fig_dendro, use_container_width=True)
                except Exception:
                    # Fallback: bar chart of merge distances (always works)
                    merge_distances = link_matrix[n - last_n:, 2]
                    fig_bar = px.bar(
                        x=list(range(1, last_n + 1)),
                        y=merge_distances,
                        labels={"x": "Merge step (last 30)", "y": "Ward distance"},
                        color=merge_distances,
                        color_continuous_scale="Blues",
                    )
                    fig_bar.update_layout(
                        coloraxis_showscale=False,
                        margin=dict(t=20, b=20, l=10, r=10),
                        height=300,
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No cluster data available for the current filter selection.")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — JOB MATCHER
# ══════════════════════════════════════════════════════════════════════════════
with tab_matcher:
    st.subheader("Job Matcher")
    st.caption("Rank jobs based on your profile.")

    with st.form("matcher_form"):
        col1, col2 = st.columns(2)
        with col1:
            user_skills   = st.text_input("Skills / keywords", placeholder="e.g. Python, data analysis, SQL")
            user_level    = st.selectbox("Your experience level", options=["Any"] + all_levels)
            user_mode     = st.selectbox("Preferred work mode", options=["Any"] + all_modes)
            user_type     = st.selectbox("Job type preference", options=["Any"] + all_types)
        with col2:
            user_exp        = st.slider("Years of experience", min_value=0.0, max_value=15.0, value=3.0, step=0.5, format="%.1f yrs")
            user_salary_min = st.number_input("Min salary (PHP/month)", min_value=0, max_value=500_000, value=40_000, step=5_000)
            user_salary_max = st.number_input("Max salary (PHP/month)", min_value=0, max_value=500_000, value=120_000, step=5_000)
            top_n           = st.slider("Number of results", min_value=3, max_value=20, value=8)

        submitted = st.form_submit_button("Find Matches", use_container_width=True)

    if submitted:
        level_filter = [] if user_level == "Any" else [user_level]
        mode_filter  = [] if user_mode  == "Any" else [user_mode]
        type_filter  = [] if user_type  == "Any" else [user_type]

        with st.spinner("Running matching engine..."):
            results = match_jobs(df=df, skill_query=user_skills, level=level_filter, mode=mode_filter,
                                 job_type=type_filter, exp_years=user_exp,
                                 salary_min=user_salary_min, salary_max=user_salary_max, top_n=top_n)

        if results.empty:
            st.warning("No jobs matched. Try adjusting your filters.")
        else:
            st.success(f"Successfully matched {len(results)} jobs.")

            st.markdown("**Match Score Breakdown**")
            fig_scores = px.bar(
                results, x="match_pct",
                y=results.index.astype(str) + ". " + results["tech_specialisation"] + " (" + results["level"] + ")",
                orientation="h", color="match_pct",
                color_continuous_scale=["#f87171", "#fbbf24", "#34d399"], range_color=[0, 100],
                labels={"match_pct": "Match %", "y": ""}, text="match_pct"
            )
            fig_scores.update_traces(texttemplate="%{text}%", textposition="outside")
            fig_scores.update_layout(coloraxis_showscale=False, yaxis=dict(autorange="reversed"),
                                      xaxis=dict(range=[0, 115]), margin=dict(t=20, b=20, l=10, r=10),
                                      height=max(300, len(results) * 42))
            st.plotly_chart(fig_scores, use_container_width=True)

            st.markdown("**Score Analysis**")
            results_long = results.copy()
            results_long["label"] = results_long["tech_specialisation"] + " (" + results_long["level"] + ")"
            fig_stacked = go.Figure()
            fig_stacked.add_trace(go.Bar(name="Skill match (max 55)", y=results_long["label"], x=results_long["skill_score"].round(1), orientation="h", marker_color="#3b82f6"))
            fig_stacked.add_trace(go.Bar(name="Salary fit (max 25)",  y=results_long["label"], x=results_long["salary_score"].round(1), orientation="h", marker_color="#10b981"))
            fig_stacked.add_trace(go.Bar(name="Experience fit (max 15)", y=results_long["label"], x=results_long["exp_score"].round(1), orientation="h", marker_color="#f59e0b"))
            fig_stacked.add_trace(go.Bar(name="Cluster boost (max 5)", y=results_long["label"], x=results_long["cluster_boost"].round(1), orientation="h", marker_color="#8b5cf6"))
            fig_stacked.update_layout(barmode="stack", legend=dict(orientation="h", yanchor="bottom", y=1.02),
                                       yaxis=dict(autorange="reversed"), xaxis=dict(title="Score breakdown", range=[0, 100]),
                                       margin=dict(t=60, b=20, l=10, r=10), height=max(300, len(results) * 42))
            st.plotly_chart(fig_stacked, use_container_width=True)

            st.markdown("**Matched Job Listings**")
            for _, row in results.iterrows():
                score = int(row["match_pct"])
                badge_class = "score-high" if score >= 70 else "score-medium" if score >= 45 else "score-low"
                exp_req = f"{row['work_experience_years']:.0f} yrs" if pd.notna(row["work_experience_years"]) else "Not specified"
                st.markdown(f"""
                <div class="match-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                        <strong style="font-size:1.05rem;">{row['tech_specialisation']}</strong>
                        <span class="score-badge {badge_class}">{score}% Match</span>
                    </div>
                    <div style="display:flex; gap:20px; flex-wrap:wrap; font-size:0.85rem;">
                        <span><strong>Level:</strong> {row['level']}</span>
                        <span><strong>Mode:</strong> {row['mode']}</span>
                        <span><strong>Type:</strong> {row['type']}</span>
                        <span><strong>Salary:</strong> PHP {row['salary_from']:,.0f} – {row['salary_to']:,.0f}/mo</span>
                        <span><strong>Education:</strong> {row['education_level']}</span>
                        <span><strong>Exp Required:</strong> {exp_req}</span>
                    </div>
                </div>""", unsafe_allow_html=True)

            st.divider()
            csv_out = results.drop(columns=["skill_score", "salary_score", "exp_score", "cluster_boost"], errors="ignore").to_csv(index=False)
            st.download_button("Download Results (CSV)", data=csv_out, file_name="matched_jobs.csv", mime="text/csv")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — AI CHATBOT
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.subheader("AI Job Assistant")
    st.caption("Ask about salaries, job demand, or say 'find me a job' to get matched via chat.")

    st.markdown("**Try asking:**")
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        if st.button("What's the average salary for a Senior Python developer?", use_container_width=True):
            st.session_state.gemini_trigger = "What's the average salary for a Senior Python developer?"
            st.rerun()
    with col_s2:
        if st.button("Find me remote jobs for someone with 3 years of Java experience", use_container_width=True):
            st.session_state.gemini_trigger = "Find me remote jobs for someone with 3 years of Java experience"
            st.rerun()
    with col_s3:
        if st.button("Which IT specialisations are most in demand?", use_container_width=True):
            st.session_state.gemini_trigger = "Which IT specialisations are most in demand?"
            st.rerun()

    st.divider()

    if st.session_state.get("chat_history"):
        if st.button("🗑️ Clear conversation"):
            st.session_state.chat_history = []
            st.rerun()

    render_chat(df)


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 4 — ADMIN PANEL
# ══════════════════════════════════════════════════════════════════════════════
if tab_admin:
    with tab_admin:
        st.subheader("Admin Panel")
        st.caption("Only visible to logged-in admins.")

        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Total rows", len(df))
        with col2: st.metric("Unique specialisations", df["tech_specialisation"].nunique())
        with col3: st.metric("Avg salary (mid)", f"PHP {df['salary_mid'].mean():,.0f}")
        with col4: st.metric("Missing exp data", int(df["work_experience_years"].isna().sum()))

        st.divider()

        st.markdown("**Full dataset (unfiltered)**")
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.download_button(
            "⬇️ Download full dataset (CSV)",
            data=df.to_csv(index=False),
            file_name="itjobs_full.csv",
            mime="text/csv",
        )

        st.divider()

        st.markdown("**Salary outlier inspector**")
        threshold = st.slider("Show jobs with salary_mid above:", 0, 500_000, 200_000,
                              step=10_000, format="PHP %d")
        outliers = df[df["salary_mid"] > threshold].sort_values("salary_mid", ascending=False)
        st.caption(f"{len(outliers)} listings above threshold")
        st.dataframe(
            outliers[["jobid", "tech_specialisation", "level", "salary_from", "salary_to", "salary_mid"]],
            use_container_width=True, hide_index=True
        )