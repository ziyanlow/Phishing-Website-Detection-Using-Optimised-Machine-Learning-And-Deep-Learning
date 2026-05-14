import streamlit as st
import pandas as pd
import plotly.express as px
import time

# =====================================
# CONFIG
# =====================================
st.set_page_config(
    page_title="PhishGuard Threat Intelligence Dashboard",
    layout="wide"
)

LOG_FILE = "logs/api_log.csv"

# =====================================
# LOAD DATA
# =====================================
@st.cache_data(ttl=2)
def load_data():
    df_ = pd.read_csv(LOG_FILE)
    df_["timestamp"] = pd.to_datetime(df_["timestamp"])
    return df_


df = load_data()

# =====================================
# CYBERSECURITY THEME CSS
# =====================================
st.markdown("""
<style>

body {
    background-color: #0d0d0d;
    color: #e4e4e4;
}

.sidebar .sidebar-content {
    background-color: #111111;
}

h1, h2, h3, h4 {
    color: #00eaff !important;
}

.metric-card {
    background: #1a1a1a;
    padding: 25px;
    border-radius: 12px;
    border: 1px solid #00eaff;
    text-align: center;
    box-shadow: 0px 0px 12px #00eaff55;
}

.metric-value {
    font-size: 32px;
    color: #00eaff;
}

.card-title {
    color: #c8f7ff;
    font-size: 18px;
}

.big-badge {
    font-size: 22px;
    padding: 10px;
    border-radius: 8px;
}

.high-risk {
    background-color: #ff0033;
    color: white;
}

.medium-risk {
    background-color: #ffaa00;
    color: black;
}

.low-risk {
    background-color: #00cc66;
    color: black;
}
</style>
""", unsafe_allow_html=True)


# =====================================
# SIDEBAR NAVIGATION + FILTERS + AUTO-REFRESH
# =====================================
st.sidebar.title("🛡️ PhishGuard Menu")
menu = st.sidebar.radio("Navigation", ["Dashboard", "Analytics", "High-Risk", "URL Detail"])

st.sidebar.markdown("---")
st.sidebar.subheader("Filters")

# Date range filter
start_date = st.sidebar.date_input("Start date", df["timestamp"].min().date())
end_date = st.sidebar.date_input("End date", df["timestamp"].max().date())

df = df[(df["timestamp"].dt.date >= start_date) & (df["timestamp"].dt.date <= end_date)]

# Label filter
label_filter = st.sidebar.multiselect(
    "Filter by label",
    options=df["label"].unique(),
    default=list(df["label"].unique())
)
df = df[df["label"].isin(label_filter)]

# Probability threshold
prob_min = st.sidebar.slider("Minimum probability", 0.0, 1.0, 0.0, 0.01)
df = df[df["probability"] >= prob_min]

st.sidebar.markdown(f"📌 Records after filter: **{len(df)}**")

st.sidebar.markdown("---")
auto_refresh = st.sidebar.checkbox("Auto-Refresh Dashboard", value=False)



# =====================================
# HELPER: Risk Levels
# =====================================
def risk_level(p):
    if p > 0.7:
        return "High"
    elif p > 0.3:
        return "Medium"
    else:
        return "Low"

if len(df) == 0:
    st.warning("No data after applying filters. Try relaxing the filters.")
    if auto_refresh:
        time.sleep(10)
        st.experimental_rerun()
else:
    df["risk"] = df["probability"].apply(risk_level)

    # =====================================
    # PAGE 1: Dashboard (Home)
    # =====================================
    if menu == "Dashboard":

        st.title("🛡️ PhishGuard — Threat Intelligence Dashboard")
        st.write("Real-time monitoring of phishing detections from browser extension.")

        # --- KPI CARDS ---
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(
                "<div class='metric-card'><div class='card-title'>Total Scans</div>"
                f"<div class='metric-value'>{len(df)}</div></div>",
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown(
                "<div class='metric-card'><div class='card-title'>Phishing Attempts</div>"
                f"<div class='metric-value'>{(df['label']=='phishing').sum()}</div></div>",
                unsafe_allow_html=True,
            )

        with col3:
            st.markdown(
                "<div class='metric-card'><div class='card-title'>Legitimate URLs</div>"
                f"<div class='metric-value'>{(df['label']=='legitimate').sum()}</div></div>",
                unsafe_allow_html=True,
            )

        with col4:
            detection_rate = (df["label"] == "phishing").mean() * 100
            st.markdown(
                "<div class='metric-card'><div class='card-title'>Phishing Rate</div>"
                f"<div class='metric-value'>{detection_rate:.1f}%</div></div>",
                unsafe_allow_html=True,
            )

        st.write("---")

        # ===============================
        # REAL-TIME API HIT METRICS
        # ===============================
        st.subheader("📡 Real-Time API Traffic")

        df_hits = df.copy()

        # Requests TODAY
        today = pd.Timestamp.now().date()
        hits_today = df_hits[df_hits["timestamp"].dt.date == today]

        # Requests per hour (last 24h)
        df_hits["hour"] = df_hits["timestamp"].dt.hour
        hits_per_hour = df_hits.groupby("hour").size().reset_index(name="count")

        # Requests per minute (last 60 minutes)
        df_hits["minute"] = df_hits["timestamp"].dt.floor("min")
        last_60 = df_hits[df_hits["timestamp"] > pd.Timestamp.now() - pd.Timedelta(minutes=60)]
        hits_per_minute = last_60.groupby("minute").size().reset_index(name="count")

        col1, col2, col3 = st.columns(3)

        col1.metric("Total API Hits", len(df_hits))
        col2.metric("Today's API Hits", len(hits_today))
        col3.metric("Last 60 Min Hits", len(last_60))

        st.write("### ⏱️ API Traffic (Hits per Hour)")
        fig_hits_hr = px.line(
            hits_per_hour,
            x="hour", y="count",
            markers=True,
            title="API Requests per Hour",
            template="plotly_dark"
        )
        st.plotly_chart(fig_hits_hr, use_container_width=True)

        st.write("### 🕒 API Traffic (Hits per Minute - Last 60 Minutes)")
        fig_hits_min = px.line(
            hits_per_minute,
            x="minute", y="count",
            markers=True,
            title="API Requests per Minute",
            template="plotly_dark"
        )
        st.plotly_chart(fig_hits_min, use_container_width=True)

        # --- ANIMATED TREND CHART ---
        st.subheader("📈 Threat Probability Timeline (Animated by Day)")

        df_anim = df.copy()
        df_anim["date"] = df_anim["timestamp"].dt.date

        daily_stats = (
            df_anim.groupby(["date", "label"])["probability"]
            .mean()
            .reset_index(name="avg_probability")
        )

        fig_anim = px.bar(
            daily_stats,
            x="label",
            y="avg_probability",
            color="label",
            animation_frame="date",
            range_y=[0, 1],
            title="Average Probability per Day",
            template="plotly_dark",
        )
        st.plotly_chart(fig_anim, use_container_width=True)

        st.write("---")

        # --- PIE CHART ---
        st.subheader("🧩 Threat Distribution")
        fig_pie = px.pie(
            df,
            names="label",
            color="label",
            color_discrete_map={"phishing": "red", "legitimate": "green"},
            template="plotly_dark",
            title="Phishing vs Legitimate",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # =====================================
    # PAGE 2: Analytics (Geo, Correlation, Anomaly)
    # =====================================
    elif menu == "Analytics":

        st.title("📊 Advanced Threat Analytics")

        # ---- Risk level distribution ----
        st.subheader("🚨 Risk Level Distribution")
        risk_count = df["risk"].value_counts()
        st.bar_chart(risk_count)

        # ---- TLD analysis ----
        st.subheader("🌐 Top Domain Endings (TLD)")
        df["tld"] = df["url"].apply(lambda u: u.split(".")[-1])
        tld_counts = df["tld"].value_counts().reset_index()
        tld_counts.columns = ["tld", "count"]

        fig_tld = px.bar(
            tld_counts.head(12),
            x="tld",
            y="count",
            title="Most Common TLDs in URLs",
            template="plotly_dark",
        )
        st.plotly_chart(fig_tld, use_container_width=True)


        # ---- ANOMALY DETECTION ON PROBABILITY ----
        st.subheader("⚠️ Anomaly Detection on Probability (Z-score > 2)")

        mean_p = df["probability"].mean()
        std_p = df["probability"].std()
        if std_p > 0:
            df["z_score"] = (df["probability"] - mean_p) / std_p
            anomalies = df[df["z_score"].abs() > 2]

            fig_anom = px.scatter(
                df,
                x="timestamp",
                y="probability",
                color="label",
                title="Probability Timeline with Anomalies",
                template="plotly_dark",
            )

            if len(anomalies) > 0:
                fig_anom.add_scatter(
                    x=anomalies["timestamp"],
                    y=anomalies["probability"],
                    mode="markers",
                    marker=dict(color="red", size=10, symbol="x"),
                    name="Anomaly",
                )

            st.plotly_chart(fig_anom, use_container_width=True)

            if len(anomalies) > 0:
                st.write("Detected Anomalies:")
                st.dataframe(
                    anomalies[["timestamp", "url", "probability", "label", "z_score"]]
                    .sort_values("timestamp", ascending=False)
                )
            else:
                st.success("No strong anomalies detected based on probability.")

        else:
            st.info("Standard deviation of probabilities is zero. Cannot compute anomalies.")

    # =====================================
    # PAGE 3: High-Risk
    # =====================================
    elif menu == "High-Risk":

        st.title("⚠️ High-Risk URLs (Probability > 70%)")

        high_risk = df[df["probability"] > 0.7]

        if len(high_risk) == 0:
            st.success("No high-risk URLs detected.")
        else:
            st.dataframe(
                high_risk.sort_values("probability", ascending=False)
            )

            # Download
            csv = high_risk.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download High-Risk Report",
                data=csv,
                file_name="high_risk_urls.csv",
                mime="text/csv",
            )

    # =====================================
    # PAGE 4: URL Detail Page
    # =====================================
    elif menu == "URL Detail":

        st.title("🔍 URL Detail Report")

        selected_url = st.selectbox("Select URL", df["url"].unique())

        record = df[df["url"] == selected_url].iloc[0]

        risk_class = record["risk"].lower()
        risk_badge = f"<span class='big-badge {risk_class}-risk'>{record['risk']} Risk</span>"

        st.markdown(f"### URL: {record['url']}")
        st.markdown(risk_badge, unsafe_allow_html=True)

        st.write("### Probability:", record["probability"])
        st.write("### Label:", record["label"])
        st.write("### Timestamp:", record["timestamp"])

        if "reasons" in df.columns:
            st.write("### Explanation:")
            for r in str(record["reasons"]).split(";"):
                r = r.strip()
                if r:
                    st.write("- ", r)

        # Show raw record
        with st.expander("Raw record"):
            st.json(record.to_dict())


# =====================================
# AUTO-REFRESH HANDLING
# =====================================
if auto_refresh:
    time.sleep(2)   # refresh every 2 seconds
    st.rerun()
