# -*- coding: utf-8 -*-
"""
Created on Wed Feb  4 15:58:17 2026

@author: lenovo
"""
st.caption("For official planning use only. Data is processed temporarily and not stored.")

import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import io, os

# ===== PDF imports =====
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors

# ================== PAGE SETUP ==================
st.set_page_config(page_title="HR Promotion & Retirement Forecast", layout="wide")
st.title("🏛 HR Promotion & Retirement Forecast System")

st.markdown("""
**Included Modules**
- Vacancy-cascade promotion logic  
- Full rank-wise promotion history  
- Year-wise & Rank-wise forecasts  
- Charts & calendar  
- Excel + A4 printable PDF  
""")

uploaded_file = st.file_uploader(
    "Upload Excel file (SNo, Name Details, DOB, Rank)",
    type=["xlsx"]
)

# ================== UTILITIES ==================
def parse_yy(d):
    d = datetime.strptime(str(d), "%d.%m.%y")
    if d.year > datetime.now().year:
        d = d.replace(year=d.year - 100)
    return d

def fmt(d):
    return d.strftime("%d-%m-%Y") if pd.notna(d) else "—"

def eligible(current_date, needed_rank):
    return [
        e for e in employees
        if not e["retired"]
        and e["rank"] == needed_rank
        and e["retire"] >= current_date
    ]

def P(text, style):
    return Paragraph(str(text), style)

# ================== PDF GENERATOR ==================
def generate_pdf(master_df, promo_df, year_df, rank_df, cal_df, title):

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=36, rightMargin=36,
        topMargin=48, bottomMargin=36
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleC", alignment=TA_CENTER, fontSize=14))
    styles.add(ParagraphStyle(name="Sec", fontSize=11, spaceBefore=10))
    styles.add(ParagraphStyle(name="Cell", fontSize=8, leading=10))

    story = []

    # Header
    story.append(Paragraph("HR PROMOTION & RETIREMENT FORECAST REPORT", styles["TitleC"]))
    story.append(Paragraph(f"Input File : {title}", styles["Normal"]))
    story.append(Paragraph(f"Generated on : {date.today().strftime('%d-%m-%Y')}", styles["Normal"]))
    story.append(Spacer(1, 12))

    def add_table(df, widths):
        rows = [[P(c, styles["Cell"]) for c in df.columns]]
        for r in df.values.tolist():
            rows.append([P(v, styles["Cell"]) for v in r])
        t = Table(rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, colors.black),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("FONT", (0,0), (-1,0), "Helvetica-Bold"),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        return t

    story.append(Paragraph("1. Master Data (All Employees)", styles["Sec"]))
    story.append(add_table(
        master_df,
        [40, 130, 60, 45, 75, 220, 35]
    ))
    story.append(PageBreak())

    story.append(Paragraph("2. Promotion History", styles["Sec"]))
    story.append(add_table(promo_df, [35,40,140,50,50,60]))
    story.append(PageBreak())

    story.append(Paragraph("3. Year-wise Forecast", styles["Sec"]))
    story.append(add_table(year_df, [120,120,120]))
    story.append(PageBreak())

    story.append(Paragraph("4. Rank-wise Forecast", styles["Sec"]))
    story.append(add_table(rank_df, [80,120,120]))
    story.append(PageBreak())

    story.append(Paragraph("5. Retirement & Promotion Calendar", styles["Sec"]))
    story.append(add_table(cal_df, [80,150,140,60]))

    doc.build(story)
    buf.seek(0)
    return buf

# ================== MAIN LOGIC ==================
if uploaded_file:

    df = pd.read_excel(uploaded_file)
    df["DOB"] = df["DOB"].apply(parse_yy)
    df["Date of Retirement"] = df["DOB"] + df["DOB"].apply(lambda _: relativedelta(years=60))

    employees = []
    for i, r in df.iterrows():
        employees.append({
            "index": i,
            "sno": int(r["SNo"]),
            "name": r["Name Details"],
            "rank": int(r["Rank"]),
            "retire": r["Date of Retirement"],
            "retired": False,
            "history": []
        })

    retire_order = sorted(range(len(employees)), key=lambda i: employees[i]["retire"])

    promo_log, calendar = [], []
    yearly = defaultdict(lambda: {"ret":0, "pro":0})
    rank_year = defaultdict(lambda: defaultdict(int))
    promo_no = 1

    for idx in retire_order:
        emp = employees[idx]
        if emp["retired"]:
            continue

        emp["retired"] = True
        y = emp["retire"].year
        yearly[y]["ret"] += 1
        calendar.append([fmt(emp["retire"]), emp["name"], f"Rank {emp['rank']}", "Retirement"])

        vac = emp["rank"]
        while True:
            pool = eligible(emp["retire"], vac-1)
            if not pool:
                break
            p = sorted(pool, key=lambda x: x["sno"])[0]
            old, new = p["rank"], p["rank"]+1
            p["rank"] = new
            p["history"].append(f"{old}→{new} on {fmt(emp['retire'])}")

            promo_log.append([promo_no, p["sno"], p["name"], old, new, fmt(emp["retire"])])
            calendar.append([fmt(emp["retire"]), p["name"], f"{old}→{new}", "Promotion"])
            yearly[y]["pro"] += 1
            rank_year[y][new] += 1

            promo_no += 1
            vac -= 1

    master_rows = []
    for e in sorted(employees, key=lambda x: x["sno"]):
        master_rows.append([
            e["sno"], e["name"], fmt(df.loc[e["index"],"DOB"]),
            df.loc[e["index"],"Rank"], fmt(e["retire"]),
            " | ".join(e["history"]) if e["history"] else "—",
            e["rank"]
        ])

    master_df = pd.DataFrame(master_rows, columns=[
        "Seniority No","Name Details","DOB","Initial Rank",
        "Date of Retirement","Rank Promotion History","Final Rank"
    ])

    promo_df = pd.DataFrame(promo_log, columns=[
        "Promo No","SNo","Name","Old Rank","New Rank","Promotion Date"
    ])

    year_df = pd.DataFrame(
        [[y, yearly[y]["ret"], yearly[y]["pro"]] for y in sorted(yearly)],
        columns=["Year","Retirements","Promotions"]
    )

    rank_df = pd.DataFrame(
        [(y,r,c) for y in rank_year for r,c in rank_year[y].items()],
        columns=["Year","Rank","Promotions"]
    )

    cal_df = pd.DataFrame(calendar, columns=["Date","Name","Event","Type"])

    # ================== UI ==================
    st.subheader("📋 Master Data")
    st.dataframe(master_df, use_container_width=True)

    st.subheader("📊 Year-wise Forecast")
    st.bar_chart(year_df.set_index("Year"))

    st.subheader("📊 Rank-wise Promotions")
    st.dataframe(rank_df)

    # ================== DOWNLOADS ==================
    base = os.path.splitext(uploaded_file.name)[0]

    excel_buf = io.BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as w:
        master_df.to_excel(w, sheet_name="Master_Data", index=False)
        promo_df.to_excel(w, sheet_name="Promotion_History", index=False)
        year_df.to_excel(w, sheet_name="Yearly_Forecast", index=False)
        rank_df.to_excel(w, sheet_name="Rank_Wise_Forecast", index=False)
        cal_df.to_excel(w, sheet_name="Calendar", index=False)
    excel_buf.seek(0)

    st.download_button("⬇ Download Excel Report", excel_buf, f"{base}_HR_Forecast.xlsx")

    pdf_buf = generate_pdf(master_df, promo_df, year_df, rank_df, cal_df, uploaded_file.name)

    st.download_button("🖨️ Download Printable PDF", pdf_buf, f"{base}_HR_Forecast_Report.pdf")

    # ================== EXIT ==================
    st.markdown("---")
    if st.button("❌ Exit Service"):
        st.success("Service ended. You may close this browser tab.")
        st.stop()

