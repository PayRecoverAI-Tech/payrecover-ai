import sqlite3
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -------------------- APP CONFIG --------------------
st.set_page_config(
    page_title="PayRecoverAI",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = "payrecoverai.db"

BG = "#0B1020"
CARD = "#151B2E"
BORDER = "#26314B"
TEXT = "#E8ECF8"
MUTED = "#8A94B2"
CYAN = "#38BDF8"
GREEN = "#22C55E"
AMBER = "#F59E0B"
RED = "#EF4444"

# -------------------- DATABASE --------------------
def connect_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer TEXT NOT NULL,
                billed REAL NOT NULL,
                collected REAL NOT NULL DEFAULT 0,
                days_pending INTEGER NOT NULL DEFAULT 0,
                record_date TEXT NOT NULL,
                notes TEXT DEFAULT ''
            )
            """
        )
        # Safe, additive migration: add the paid-list flag only if it is missing.
        # Existing payment rows and amounts are not replaced or deleted.
        columns = [row[1] for row in conn.execute("PRAGMA table_info(payments)").fetchall()]
        if "moved_to_paid_list" not in columns:
            conn.execute(
                "ALTER TABLE payments ADD COLUMN moved_to_paid_list INTEGER NOT NULL DEFAULT 0"
            )
        conn.commit()

def load_payments():
    with connect_db() as conn:
        df = pd.read_sql_query("SELECT * FROM payments ORDER BY id DESC", conn)
    if not df.empty:
        df["record_date"] = pd.to_datetime(df["record_date"]).dt.date
    return df

def add_payment(customer, billed, collected, days_pending, record_date, notes):
    with connect_db() as conn:
        conn.execute(
            """INSERT INTO payments
               (customer, billed, collected, days_pending, record_date, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (customer.strip(), float(billed), float(collected), int(days_pending),
             record_date.isoformat(), notes.strip()),
        )
        conn.commit()

def update_payment(record_id, customer, billed, collected, days_pending, record_date, notes):
    with connect_db() as conn:
        conn.execute(
            """UPDATE payments
               SET customer = ?, billed = ?, collected = ?, days_pending = ?, record_date = ?, notes = ?
               WHERE id = ?""",
            (customer.strip(), float(billed), float(collected), int(days_pending),
             record_date.isoformat(), notes.strip(), int(record_id)),
        )
        conn.commit()

def delete_payment(record_id):
    with connect_db() as conn:
        conn.execute("DELETE FROM payments WHERE id = ?", (int(record_id),))
        conn.commit()

init_db()

# -------------------- HELPERS --------------------
def money(value):
    return f"₹{value:,.0f}"

def add_derived_columns(df):
    if df.empty:
        return df
    df = df.copy()
    df["outstanding"] = (df["billed"] - df["collected"]).clip(lower=0)
    df["status"] = df.apply(
        lambda r: "Paid" if r["outstanding"] <= 0 else (
            "Overdue" if int(r["days_pending"]) > 7 else "Pending"
        ), axis=1
    )
    df["risk"] = df.apply(
        lambda r: "Low" if r["status"] == "Paid" or int(r["days_pending"]) <= 3
        else ("Medium" if int(r["days_pending"]) <= 7 else "High"), axis=1
    )
    df["collection_pct"] = df.apply(
        lambda r: min(100, max(0, (r["collected"] / r["billed"] * 100) if r["billed"] else 0)),
        axis=1
    )
    if "moved_to_paid_list" not in df.columns:
        df["moved_to_paid_list"] = 0
    df["moved_to_paid_list"] = df["moved_to_paid_list"].fillna(0).astype(int)
    df["record_date"] = pd.to_datetime(df["record_date"]).dt.date
    return df

def status_color(status):
    return {"Paid": GREEN, "Pending": AMBER, "Overdue": RED}.get(status, MUTED)

def risk_color(risk):
    return {"Low": GREEN, "Medium": AMBER, "High": RED}.get(risk, MUTED)

# -------------------- STYLE --------------------
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    .stApp {{ background: {BG}; color: {TEXT}; }}
    [data-testid="stSidebar"] {{ background: #0E1628; border-right: 1px solid {BORDER}; }}
    [data-testid="stMetric"] {{
        background: {CARD}; border: 1px solid {BORDER}; padding: 18px 20px;
        border-radius: 14px;
    }}
    [data-testid="stMetricLabel"] {{ color: {MUTED}; }}
    [data-testid="stMetricValue"] {{ color: {TEXT}; font-weight: 800; }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        border-color: {BORDER} !important; border-radius: 14px !important;
    }}
    .top-subtitle {{ color: {MUTED}; font-size: 0.9rem; }}
    .insight {{
        background: linear-gradient(110deg, #17243A, #151B2E);
        border: 1px solid #2B4564; border-left: 4px solid {CYAN};
        border-radius: 14px; padding: 16px 18px; margin: 8px 0 18px 0;
    }}
    .small-muted {{ color: {MUTED}; font-size: 0.82rem; }}
    .pill {{ padding: 3px 8px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; }}
    .stButton > button {{ border-radius: 9px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------- SIDEBAR --------------------
with st.sidebar:
    st.markdown("## 💳 PayRecoverAI")
    st.caption("Payment recovery workspace")
    st.divider()

    with st.expander("➕ Add payment record", expanded=True):
        with st.form("add_payment_form", clear_on_submit=True):
            customer = st.text_input("Customer name", placeholder="e.g. Rahul")
            billed = st.number_input("Total billed (₹)", min_value=0.0, value=5000.0, step=500.0)
            collected = st.number_input("Amount collected (₹)", min_value=0.0, value=0.0, step=500.0)
            days_pending = st.number_input("Days since payment became due", min_value=0, max_value=3650, value=0, step=1)
            record_date = st.date_input("Record date", value=date.today())
            notes = st.text_input("Notes (optional)")
            submitted = st.form_submit_button("Save payment", type="primary", use_container_width=True)
            if submitted:
                if not customer.strip():
                    st.error("Please enter a customer name.")
                elif billed <= 0:
                    st.error("Total billed must be greater than ₹0.")
                elif collected > billed:
                    st.error("Collected amount cannot exceed the total billed amount.")
                else:
                    add_payment(customer, billed, collected, days_pending, record_date, notes)
                    st.success(f"Saved payment record for {customer.strip()}.")
                    st.rerun()

    st.divider()
    st.markdown("### 🔎 Filters")
    today = date.today()
    start_default = today - timedelta(days=365)
    date_range = st.date_input(
        "Date range", value=(start_default, today), key="filter_dates"
    )
    risk_filter = st.multiselect("Risk level", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    status_filter = st.multiselect("Payment status", ["Overdue", "Pending", "Paid"], default=["Overdue", "Pending", "Paid"])
    st.divider()
    st.markdown("### ⏳ Recovery deadline")
    max_overdue_days = st.number_input(
        "Maximum overdue days", min_value=1, max_value=3650, value=90, step=1,
        help="Customers whose unpaid balance is older than this limit are flagged."
    )

# -------------------- LOAD AND FILTER --------------------
raw_df = load_payments()
df = add_derived_columns(raw_df)

if not df.empty:
    customer_options = sorted(df["customer"].dropna().unique().tolist())
    customer_filter = st.sidebar.multiselect("Customer", customer_options, default=customer_options)
    amount_filter = st.sidebar.selectbox(
        "Outstanding amount",
        ["All amounts", "Below ₹50,000", "₹50,000–₹99,999", "₹1,00,000–₹1,99,999", "₹2,00,000 and above", "Custom range"],
        key="outstanding_amount_filter",
    )
    custom_min = custom_max = None
    if amount_filter == "Custom range":
        custom_min, custom_max = st.sidebar.slider(
            "Custom outstanding range (₹)", min_value=0, max_value=max(50000, int(df["outstanding"].max()) + 1),
            value=(0, max(50000, int(df["outstanding"].max()) + 1)), step=5000, key="custom_outstanding_range"
        )
    filtered = df.copy()

    # Filter by outstanding balance (billed minus collected), not the original invoice total.
    if amount_filter == "Below ₹50,000":
        filtered = filtered[(filtered["outstanding"] > 0) & (filtered["outstanding"] < 50000)]
    elif amount_filter == "₹50,000–₹99,999":
        filtered = filtered[(filtered["outstanding"] >= 50000) & (filtered["outstanding"] < 100000)]
    elif amount_filter == "₹1,00,000–₹1,99,999":
        filtered = filtered[(filtered["outstanding"] >= 100000) & (filtered["outstanding"] < 200000)]
    elif amount_filter == "₹2,00,000 and above":
        filtered = filtered[filtered["outstanding"] >= 200000]
    elif amount_filter == "Custom range":
        filtered = filtered[(filtered["outstanding"] >= custom_min) & (filtered["outstanding"] <= custom_max)]

    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[(filtered["record_date"] >= start_date) & (filtered["record_date"] <= end_date)]
    if risk_filter:
        filtered = filtered[filtered["risk"].isin(risk_filter)]
    else:
        filtered = filtered.iloc[0:0]
    if status_filter:
        filtered = filtered[filtered["status"].isin(status_filter)]
    else:
        filtered = filtered.iloc[0:0]
    filtered = filtered[filtered["customer"].isin(customer_filter)] if customer_filter else filtered.iloc[0:0]
else:
    customer_filter = []
    amount_filter = "All amounts"
    filtered = df

# -------------------- HEADER --------------------
left, right = st.columns([3, 1])
with left:
    st.markdown("# 💳 PayRecoverAI")
    st.markdown('<div class="top-subtitle">Payment recovery & collection analytics</div>', unsafe_allow_html=True)
with right:
    st.markdown(
        f'<div style="text-align:right;padding-top:16px;color:{MUTED};font-size:0.82rem;">'
        f'Last updated<br><b style="color:{TEXT}">{datetime.now().strftime("%d %b %Y, %I:%M %p")}</b></div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# -------------------- KPIS --------------------
if filtered.empty:
    total_billed = collected_total = pending_total = high_risk_total = 0.0
    collection_pct = 0.0
    overdue_total = 0.0
else:
    total_billed = float(filtered["billed"].sum())
    collected_total = float(filtered["collected"].sum())
    pending_total = float(filtered["outstanding"].sum())
    overdue_total = float(filtered.loc[filtered["status"] == "Overdue", "outstanding"].sum())
    high_risk_total = float(filtered.loc[filtered["risk"] == "High", "outstanding"].sum())
    collection_pct = (collected_total / total_billed * 100) if total_billed else 0.0

st.markdown("### Collection overview")
k1, k2, k3, k4 = st.columns(4)
k1.metric("🧾 Total billed", money(total_billed), help="Total billed amount in the selected filters.")
k2.metric("✅ Collected", money(collected_total), f"{collection_pct:.1f}% of billed")
k3.metric("🟡 Pending", money(pending_total), f"Overdue: {money(overdue_total)}")
k4.metric("🔴 High-risk amount", money(high_risk_total), help="Outstanding amount classified as high risk.")

# -------------------- OVERDUE LIMIT / FINAL REMINDER --------------------
st.markdown("### ⏳ Overdue limit watch")
if not df.empty:
    deadline_df = df[(df["outstanding"] > 0) & (df["days_pending"] > int(max_overdue_days))].copy()
    d1, d2, d3 = st.columns(3)
    d1.metric("Limit", f"{int(max_overdue_days)} days")
    d2.metric("Customers beyond limit", str(len(deadline_df)))
    d3.metric("Outstanding beyond limit", money(deadline_df["outstanding"].sum() if not deadline_df.empty else 0))
    if not deadline_df.empty:
        deadline_df["Final action"] = "Review account and follow company policy"
        st.dataframe(
            deadline_df[["id", "customer", "outstanding", "days_pending", "status", "risk", "notes"]].rename(columns={
                "id":"ID", "customer":"Customer", "outstanding":"Outstanding (₹)",
                "days_pending":"Days overdue", "status":"Status", "risk":"Risk", "notes":"Notes"
            }), use_container_width=True, hide_index=True
        )
        selected_final_id = st.selectbox(
            "Prepare a final reminder for", deadline_df["id"].tolist(),
            format_func=lambda x: f"{deadline_df.loc[deadline_df['id']==x, 'customer'].iloc[0]} — {money(deadline_df.loc[deadline_df['id']==x, 'outstanding'].iloc[0])}",
            key="final_reminder_customer"
        )
        final_row = deadline_df.loc[deadline_df["id"] == selected_final_id].iloc[0]
        final_message = (
            f"Dear {final_row['customer']}, our records show an outstanding balance of {money(final_row['outstanding'])}, "
            f"which is {int(final_row['days_pending'])} days overdue and exceeds our {int(max_overdue_days)}-day payment limit. "
            "Please contact us and arrange settlement promptly. If payment has already been made, please share the payment details. "
            "Any further action will be handled in accordance with our agreement and company policy. Thank you."
        )
        st.text_area("Editable final reminder preview (not sent automatically)", value=final_message, height=140, key="final_reminder_preview")
        st.caption("This only prepares a message for review; it does not send email, SMS, WhatsApp, or take legal action.")
    else:
        st.success("No unpaid records currently exceed the selected overdue limit.")
else:
    st.info("Add or import records to use the overdue limit watch.")

with st.expander("🧪 Recovery what-if simulator", expanded=False):
    st.caption("Estimate the effect of recovering a portion of the currently outstanding balance. This is a scenario, not a prediction.")
    recovery_rate = st.slider("Assumed recovery rate", min_value=0, max_value=100, value=20, step=5, format="%d%%", key="what_if_recovery_rate")
    scenario_amount = pending_total * recovery_rate / 100
    sc1, sc2 = st.columns(2)
    sc1.metric("Estimated additional collections", money(scenario_amount))
    sc2.metric("Remaining outstanding after scenario", money(max(0, pending_total - scenario_amount)))

# -------------------- AI INSIGHT --------------------
st.markdown("### ✨ Recovery priority")
if not filtered.empty:
    outstanding_df = filtered[filtered["outstanding"] > 0].sort_values(
        ["risk", "days_pending", "outstanding"], ascending=[False, False, False]
    )
    if not outstanding_df.empty:
        first = outstanding_df.iloc[0]
        priority = first["risk"]
        pcolor = risk_color(priority)
        if first["status"] == "Overdue":
            timing_phrase = f"overdue by {int(first['days_pending'])} days"
        else:
            timing_phrase = "currently pending"
        if int(first["days_pending"]) > int(max_overdue_days):
            risk_reason = f"Beyond the {int(max_overdue_days)}-day company limit ({int(first['days_pending'])} days overdue)."
            recommended_action = "Review the account and prepare a final reminder under company policy."
        elif first["risk"] == "High":
            risk_reason = f"High risk because the unpaid balance has been overdue for {int(first['days_pending'])} days."
            recommended_action = "Prioritise a polite follow-up and verify whether a dispute or payment delay exists."
        elif first["risk"] == "Medium":
            risk_reason = f"Medium risk because the balance has been pending for {int(first['days_pending'])} days."
            recommended_action = "Send a routine reminder and confirm the expected payment date."
        else:
            risk_reason = "Low risk based on the current days-pending rule."
            recommended_action = "Use a standard reminder if the due date has passed."
        professional_message = (
            f"Dear {first['customer']}, our records show an outstanding payment of "
            f"{money(first['outstanding'])}, {timing_phrase}. Please arrange payment at "
            "your earliest convenience. If you have already paid, please disregard this "
            "message. Thank you."
        )
        st.markdown(
            f"""<div class="insight">
            <div style="color:{pcolor};font-weight:800;font-size:0.78rem;letter-spacing:0.08em;">{priority.upper()} PRIORITY</div>
            <div style="font-size:1.1rem;font-weight:700;margin:5px 0;">Follow up with {first['customer']} first</div>
            <div style="color:{MUTED};">Outstanding: <b style="color:{TEXT}">{money(first['outstanding'])}</b>
            · {int(first['days_pending'])} days since due · Status: {first['status']}</div>
            <div style="margin-top:10px;font-weight:700;">Why this customer is flagged</div>
            <div style="margin-top:4px;">{risk_reason}</div>
            <div style="margin-top:8px;font-weight:700;">Recommended next action</div>
            <div style="margin-top:4px;">{recommended_action}</div>
            <div style="margin-top:10px;font-weight:700;">Suggested professional message</div>
            <div style="margin-top:5px;">{professional_message}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        with st.expander("📋 View / copy reminder message"):
            st.text_area("Customer reminder", value=professional_message, height=150, key="professional_reminder_message")
    else:
        st.success("All visible customer balances are fully collected. No recovery follow-up is needed.")
else:
    st.info("Add a payment record from the sidebar to start populating your dashboard.")

# -------------------- COLLECTION GAUGE AND LINE --------------------
st.markdown("### 📈 Collection performance")
chart1, chart2 = st.columns([1, 1.5])
with chart1:
    fig_gauge = go.Figure(go.Pie(
        values=[collection_pct, max(0, 100 - collection_pct)],
        labels=["Collected", "Remaining"],
        hole=0.76,
        sort=False,
        direction="clockwise",
        marker=dict(colors=[CYAN, "#26314B"]),
        textinfo="none",
        hovertemplate="%{label}: %{value:.1f}%<extra></extra>",
    ))
    fig_gauge.update_layout(
        annotations=[dict(text=f"<b>{collection_pct:.0f}%</b><br><span style='font-size:11px'>collected</span>",
                          x=0.5, y=0.5, font=dict(size=28, color=TEXT), showarrow=False)],
        showlegend=False, margin=dict(t=12, b=12, l=12, r=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=300,
        font=dict(color=TEXT),
    )
    st.plotly_chart(fig_gauge, use_container_width=True)
with chart2:
    # This line chart uses daily collected values and a user-entered target.
    target = st.number_input("Collection target for selected records (₹)", min_value=0.0, value=total_billed * 0.8, step=500.0, key="collection_target")
    if not filtered.empty:
        daily = filtered.groupby("record_date", as_index=False)["collected"].sum().sort_values("record_date")
        daily["target"] = target
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=daily["record_date"], y=daily["collected"], mode="lines+markers",
            name="Collected", line=dict(color=CYAN, width=3), marker=dict(size=7),
            hovertemplate="%{x|%d %b %Y}<br>Collected: ₹%{y:,.0f}<extra></extra>",
        ))
        fig_line.add_trace(go.Scatter(
            x=daily["record_date"], y=daily["target"], mode="lines",
            name="Target", line=dict(color=AMBER, width=2, dash="dash"),
            hovertemplate="%{x|%d %b %Y}<br>Target: ₹%{y:,.0f}<extra></extra>",
        ))
        fig_line.update_layout(
            height=300, margin=dict(t=15, b=15, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=TEXT), legend=dict(orientation="h", y=1.12, x=0),
            xaxis=dict(showgrid=False, title="Record date"),
            yaxis=dict(gridcolor=BORDER, title="Amount (₹)", tickprefix="₹"),
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("Add records to see collection performance.")

# -------------------- CUSTOMER TABLE / PAID LIST --------------------
st.markdown("### 👥 Customer management")

# The bulk action applies to all saved records, not just the current chart filters.
not_moved_paid = df[(df["outstanding"] <= 0) & (df["moved_to_paid_list"] == 0)] if not df.empty else df

if not not_moved_paid.empty:
    st.info(f"{len(not_moved_paid)} fully paid record(s) are ready to move to the Paid Customers list.")
    if st.button("✅ Move All Fully Paid Customers to Paid List", type="primary", key="move_all_paid"):
        st.session_state["confirm_move_paid"] = True

if st.session_state.get("confirm_move_paid", False):
    count_to_move = len(not_moved_paid)
    st.warning(
        f"Confirm moving {count_to_move} fully paid record(s) to the Paid Customers list? "
        "Unpaid and partially paid records will stay in Pending Customers. No payment records will be deleted."
    )
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Confirm move", type="primary", key="confirm_move_paid_button"):
            with connect_db() as conn:
                conn.execute(
                    "UPDATE payments SET moved_to_paid_list = 1 "
                    "WHERE collected >= billed AND moved_to_paid_list = 0"
                )
                conn.commit()
            st.session_state["confirm_move_paid"] = False
            st.success(f"Moved {count_to_move} fully paid record(s) to Paid Customers.")
            st.rerun()
    with cancel_col:
        if st.button("Cancel", key="cancel_move_paid_button"):
            st.session_state["confirm_move_paid"] = False
            st.rerun()

pending_view, paid_view = st.tabs(["📋 Pending Customers", "🟢 Paid Customers"])

with pending_view:
    pending_table = filtered[filtered["moved_to_paid_list"] == 0].copy() if not filtered.empty else filtered
    if not pending_table.empty:
        pending_table = pending_table.sort_values(["risk", "days_pending"], ascending=[False, False])
        st.caption("Includes unpaid, partially paid, and fully paid records until the bulk move is confirmed.")
        for _, row in pending_table.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1.5, 1, 1, 2])
                with c1:
                    st.markdown(f"**{row['customer']}**")
                    st.caption(f"{row['record_date'].strftime('%d %b %Y')}")
                with c2:
                    st.markdown(f"**{money(row['outstanding'])}**")
                    st.caption("Outstanding")
                with c3:
                    sc = status_color(row["status"])
                    rc = risk_color(row["risk"])
                    st.markdown(f"<span style='color:{sc};font-weight:700'>● {row['status']}</span>", unsafe_allow_html=True)
                    st.markdown(f"<span style='color:{rc};font-size:0.82rem'>● {row['risk']} risk</span>", unsafe_allow_html=True)
                with c4:
                    st.markdown(f"<div class='small-muted'>Collection progress · {row['collection_pct']:.0f}%</div>", unsafe_allow_html=True)
                    st.progress(int(row["collection_pct"]), text=f"{row['collection_pct']:.0f}%")
        st.markdown("#### Detailed pending records")
        display_df = pending_table[["id", "customer", "record_date", "billed", "collected", "outstanding", "days_pending", "status", "risk", "collection_pct"]].copy()
        display_df = display_df.rename(columns={
            "id": "ID", "customer": "Customer", "record_date": "Date", "billed": "Billed (₹)",
            "collected": "Collected (₹)", "outstanding": "Outstanding (₹)", "days_pending": "Days since due",
            "status": "Status", "risk": "Risk", "collection_pct": "Collected %",
        })
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.success("No pending-list records match the current filters.")

with paid_view:
    paid_table = filtered[filtered["moved_to_paid_list"] == 1].copy() if not filtered.empty else filtered
    if not paid_table.empty:
        st.markdown(
            "<div style='background:#123B2D;border:1px solid #166534;border-radius:12px;"
            "padding:12px 16px;color:#BBF7D0;font-weight:700;margin-bottom:12px;'>"
            "✓ Paid Customers · Fully paid records moved here by the company</div>",
            unsafe_allow_html=True,
        )
        paid_table = paid_table.sort_values(["record_date", "customer"], ascending=[False, True])
        paid_display = paid_table[["id", "customer", "record_date", "billed", "collected", "outstanding", "status"]].copy()
        paid_display = paid_display.rename(columns={
            "id": "ID", "customer": "Customer", "record_date": "Date", "billed": "Billed (₹)",
            "collected": "Paid amount (₹)", "outstanding": "Outstanding (₹)", "status": "Status",
        })
        st.dataframe(paid_display, use_container_width=True, hide_index=True)
        st.caption("These records remain in the database. Only their list placement has changed.")
        if st.button("↩ Return All Paid-List Records to Pending Customers", key="return_paid_list"):
            st.session_state["confirm_return_paid"] = True
        if st.session_state.get("confirm_return_paid", False):
            st.warning("Return all records in the Paid Customers list to Pending Customers? Their payment details will remain unchanged.")
            return_col, cancel_return_col = st.columns(2)
            with return_col:
                if st.button("Confirm return", key="confirm_return_paid_button"):
                    with connect_db() as conn:
                        conn.execute("UPDATE payments SET moved_to_paid_list = 0 WHERE moved_to_paid_list = 1")
                        conn.commit()
                    st.session_state["confirm_return_paid"] = False
                    st.rerun()
            with cancel_return_col:
                if st.button("Cancel return", key="cancel_return_paid_button"):
                    st.session_state["confirm_return_paid"] = False
                    st.rerun()
    else:
        st.info("No customers have been moved to the Paid Customers list yet.")

# -------------------- RISK TREEMAP AND OVERDUE TIMELINE --------------------
st.markdown("### 🧭 Risk exposure")
risk_col, overdue_col = st.columns(2)
with risk_col:
    if not filtered.empty:
        risk_data = filtered[filtered["outstanding"] > 0].copy()
        if not risk_data.empty:
            fig_tree = px.treemap(
                risk_data, path=["risk", "customer"], values="outstanding",
                color="risk",
                    color_discrete_map={"Low": "#22C55E", "Medium": "#F59E0B", "High": "#EF4444"},
                    hover_data={"outstanding": ":,.0f", "days_pending": True, "status": True},
                
            )
            fig_tree.update_traces(
                texttemplate="%{label}<br>₹%{value:,.0f}",
                hovertemplate="<b>%{label}</b><br>Outstanding: ₹%{value:,.0f}<extra></extra>",
            )
            fig_tree.update_layout(
                height=350, margin=dict(t=10, b=10, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT),
            )
            st.plotly_chart(fig_tree, use_container_width=True)
        else:
            st.info("No outstanding balances in the selected records.")
    else:
        st.info("No records to display.")
with overdue_col:
    if not filtered.empty:
        overdue = filtered[filtered["status"] == "Overdue"].sort_values("days_pending", ascending=True)
        if not overdue.empty:
            fig_overdue = px.bar(
                overdue, x="days_pending", y="customer", orientation="h",
                color="risk", color_discrete_map={"Low": GREEN, "Medium": AMBER, "High": RED},
                hover_data={"outstanding": ":,.0f", "days_pending": True, "status": True},
                labels={"days_pending": "Days since due", "customer": "Customer", "risk": "Risk"},
            )
            fig_overdue.update_layout(
                height=350, margin=dict(t=10, b=10, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=TEXT), xaxis=dict(gridcolor=BORDER),
            )
            st.plotly_chart(fig_overdue, use_container_width=True)
        else:
            st.info("No overdue customers in the selected records.")
    else:
        st.info("No records to display.")

# -------------------- BULK IMPORT --------------------
with st.expander("📥 Import payment records (CSV / Excel)", expanded=False):
    st.caption("Required columns: customer, billed, collected, days_pending. Optional: record_date, notes. Import adds records; it does not replace existing records.")
    upload = st.file_uploader("Choose CSV or Excel file", type=["csv", "xlsx"], key="payment_bulk_upload")
    if upload is not None:
        try:
            import_df = pd.read_csv(upload) if upload.name.lower().endswith(".csv") else pd.read_excel(upload)
            import_df.columns = [str(c).strip().lower() for c in import_df.columns]
            required = {"customer", "billed", "collected", "days_pending"}
            missing = required - set(import_df.columns)
            if missing:
                st.error("Missing required columns: " + ", ".join(sorted(missing)))
            else:
                st.write("Preview", import_df.head(10))
                if st.button("Import previewed records", type="primary", key="confirm_bulk_import"):
                    imported = 0
                    for _, rr in import_df.iterrows():
                        customer_value = str(rr.get("customer", "")).strip()
                        billed_value = float(rr.get("billed", 0) or 0)
                        collected_value = float(rr.get("collected", 0) or 0)
                        days_value = int(float(rr.get("days_pending", 0) or 0))
                        date_value = rr.get("record_date", date.today())
                        if pd.isna(date_value) or str(date_value).strip() == "":
                            date_value = date.today()
                        else:
                            date_value = pd.to_datetime(date_value).date()
                        notes_value = "" if pd.isna(rr.get("notes", "")) else str(rr.get("notes", ""))
                        if customer_value and billed_value > 0 and 0 <= collected_value <= billed_value and days_value >= 0:
                            add_payment(customer_value, billed_value, collected_value, days_value, date_value, notes_value)
                            imported += 1
                    st.success(f"Imported {imported} valid records. Existing records were preserved.")
                    st.rerun()
        except Exception as exc:
            st.error(f"Could not read this file: {exc}")

# -------------------- RECORD MANAGEMENT --------------------
with st.expander("⚙️ Manage records", expanded=False):
    st.caption("Records are stored locally in payrecoverai.db, so they should remain after restarting the app on this computer.")
    if not raw_df.empty:
        ids = raw_df["id"].tolist()
        edit_id = st.selectbox(
            "Select a record to edit",
            ids,
            format_func=lambda x: f"#{x} — {raw_df.loc[raw_df['id'] == x, 'customer'].iloc[0]} — {money(raw_df.loc[raw_df['id'] == x, 'billed'].iloc[0])}",
            key="edit_record_id",
        )
        edit_row = raw_df.loc[raw_df["id"] == edit_id].iloc[0]
        st.markdown("#### ✏️ Edit existing payment")
        with st.form("edit_payment_form"):
            edit_customer = st.text_input("Customer name", value=str(edit_row["customer"]), key=f"edit_customer_{edit_id}")
            edit_billed = st.number_input("Total billed (₹)", min_value=0.0, value=float(edit_row["billed"]), step=500.0, key=f"edit_billed_{edit_id}")
            edit_collected = st.number_input("Amount collected (₹)", min_value=0.0, value=float(edit_row["collected"]), step=500.0, key=f"edit_collected_{edit_id}")
            edit_days = st.number_input("Days since payment became due", min_value=0, max_value=3650, value=int(edit_row["days_pending"]), step=1, key=f"edit_days_{edit_id}")
            existing_date = edit_row["record_date"]
            if not isinstance(existing_date, date):
                existing_date = pd.to_datetime(existing_date).date()
            edit_date = st.date_input("Record date", value=existing_date, key=f"edit_date_{edit_id}")
            edit_notes = st.text_input("Notes (optional)", value="" if pd.isna(edit_row.get("notes", "")) else str(edit_row.get("notes", "")), key=f"edit_notes_{edit_id}")
            update_submitted = st.form_submit_button("Update existing record", type="primary", use_container_width=True)
            if update_submitted:
                if not edit_customer.strip():
                    st.error("Please enter a customer name.")
                elif edit_billed <= 0:
                    st.error("Total billed must be greater than ₹0.")
                elif edit_collected > edit_billed:
                    st.error("Collected amount cannot exceed the total billed amount.")
                else:
                    update_payment(edit_id, edit_customer, edit_billed, edit_collected, edit_days, edit_date, edit_notes)
                    st.success(f"Updated payment record for {edit_customer.strip()}.")
                    st.rerun()

        st.divider()
        delete_id = st.selectbox("Select record ID to delete", ids, format_func=lambda x: f"#{x} — {raw_df.loc[raw_df['id'] == x, 'customer'].iloc[0]}", key="delete_record_id")
        if st.button("Delete selected record", type="secondary"):
            delete_payment(delete_id)
            st.success("Record deleted.")
            st.rerun()
        if st.button("Clear ALL records", type="secondary"):
            st.session_state["confirm_clear"] = True
        if st.session_state.get("confirm_clear", False):
            st.warning("This will permanently delete every payment record in the local database.")
            confirm_col1, confirm_col2 = st.columns(2)
            with confirm_col1:
                if st.button("Yes, clear all records", type="primary"):
                    with connect_db() as conn:
                        conn.execute("DELETE FROM payments")
                        conn.commit()
                    st.session_state["confirm_clear"] = False
                    st.rerun()
            with confirm_col2:
                if st.button("Cancel"):
                    st.session_state["confirm_clear"] = False
                    st.rerun()
    else:
        st.write("There are currently no saved records.")

st.markdown("---")
st.caption("PayRecoverAI is a demonstration dashboard. It does not connect to Razorpay or process real payments.")
