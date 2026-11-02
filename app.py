from pathlib import Path
import re
import warnings

import pandas as pd
import gradio as gr
from fastapi import FastAPI

warnings.filterwarnings("ignore")

# Keep this Excel file in the repository root, beside app.py.
DATA_FILE = Path(__file__).resolve().parent / "tech_financials_2023_2025.xlsx"

REQUIRED_SOURCE_COLUMNS = [
    "Company",
    "Fiscal Year",
    "Total Revenue ($M)",
    "Net Income ($M)",
    "Total Assets ($M)",
    "Total Liabilities ($M)",
    "CF from Operations ($M)",
]

if not DATA_FILE.exists():
    raise FileNotFoundError(
        f"Dataset not found: {DATA_FILE.name}. "
        "Upload tech_financials_2023_2025.xlsx to the GitHub repository root."
    )

# The original notebook reads the workbook with header=1.
source_df = pd.read_excel(DATA_FILE, header=1)
missing = [column for column in REQUIRED_SOURCE_COLUMNS if column not in source_df.columns]
if missing:
    raise ValueError(
        "The Excel file does not have the expected columns: "
        + ", ".join(missing)
        + ". Check that the correct workbook is in the repository."
    )

df = source_df[REQUIRED_SOURCE_COLUMNS].copy()
df.columns = [
    "Company",
    "Year",
    "Revenue",
    "Net Income",
    "Assets",
    "Liabilities",
    "Operating Cash Flow",
]

numeric_cols = [
    "Revenue",
    "Net Income",
    "Assets",
    "Liabilities",
    "Operating Cash Flow",
]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df["Year"] = (
    df["Year"].astype(str).str.replace("FY", "", regex=False).str.strip()
)
df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
df = df.dropna(subset=["Company", "Year"]).copy()
df["Year"] = df["Year"].astype(int)
df = df.sort_values(["Company", "Year"]).reset_index(drop=True)

if df.empty:
    raise ValueError("The Excel workbook loaded, but it contains no usable financial rows.")

SUPPORTED_COMPANIES = sorted(df["Company"].astype(str).unique().tolist())
LATEST_YEAR = int(df["Year"].max())

financial_definitions = {
    "Revenue": "Revenue is the total income generated from a company's core business operations before deducting expenses.",
    "Net Income": "Net Income is the company's profit after subtracting all operating costs, taxes, and other expenses.",
    "Assets": "Assets are resources owned by a company that have economic value and can generate future benefits.",
    "Liabilities": "Liabilities are financial obligations or debts that a company owes to others.",
    "Operating Cash Flow": "Operating Cash Flow represents the cash generated from a company's normal business operations.",
}

def extract_company(query: str):
    query = query.lower()
    aliases = {
        "Microsoft": ["microsoft", "msft"],
        "Apple": ["apple", "aapl"],
        "Tesla": ["tesla", "tsla"],
    }
    companies = []
    for company, names in aliases.items():
        if any(re.search(r"\b" + re.escape(name) + r"\b", query) for name in names):
            # Match the canonical name used in the workbook, case-insensitively.
            actual = next((x for x in SUPPORTED_COMPANIES if x.lower() == company.lower()), None)
            if actual:
                companies.append(actual)
    return companies

def extract_metric(query: str):
    query = query.lower()
    metric_map = {
        "Revenue": ["revenue", "sales", "turnover", "top line"],
        "Net Income": ["net income", "profit", "profits", "earnings", "net profit", "bottom line"],
        "Assets": ["assets", "asset"],
        "Liabilities": ["liabilities", "liability", "debt", "debts", "obligations"],
        "Operating Cash Flow": ["operating cash flow", "cash flow", "cash generated", "cash from operations", "ocf"],
    }
    for metric, words in metric_map.items():
        for word in sorted(words, key=len, reverse=True):
            if re.search(r"\b" + re.escape(word) + r"\b", query):
                return metric
    return None

def extract_year(query: str):
    years = re.findall(r"\b20\d{2}\b", query)
    available_years = set(df["Year"].unique())
    if years and int(years[0]) in available_years:
        return int(years[0])
    return LATEST_YEAR

def detect_intent(query: str):
    q = query.lower()
    if any(x in q for x in ["what is", "define", "meaning", "explain"]):
        return "definition"
    if any(x in q for x in ["compare", "comparison", "versus", "vs"]):
        return "compare"
    if any(x in q for x in ["highest", "largest", "maximum", "top"]):
        return "highest"
    if any(x in q for x in ["lowest", "smallest", "minimum", "least"]):
        return "lowest"
    if any(x in q for x in ["trend", "growth", "over years", "history"]):
        return "trend"
    if any(x in q for x in ["report", "statement"]):
        return "report"
    if any(x in q for x in ["summary", "summarize"]):
        return "summary"
    if any(x in q for x in ["insight", "analysis", "performance", "health"]):
        return "insight"
    if any(x in q for x in ["help", "what can you do"]):
        return "help"
    return "data"

def validate_query(query: str):
    intent = detect_intent(query)
    companies = extract_company(query)
    metric = extract_metric(query)

    if intent in ["definition", "help"]:
        return True, ""
    if intent in ["highest", "lowest", "compare"]:
        if metric:
            return True, ""
        return False, "Please specify a financial metric."
    if intent == "trend" and not metric:
        return False, "Please specify a financial metric for the trend."
    if not companies:
        return False, "I currently support only Microsoft, Apple, and Tesla."
    return True, ""

def parse_query(query: str):
    return {
        "intent": detect_intent(query),
        "companies": extract_company(query),
        "metric": extract_metric(query),
        "year": extract_year(query),
    }

def get_company_data(company, year=LATEST_YEAR):
    data = df[(df["Company"].str.lower() == str(company).lower()) & (df["Year"] == year)]
    if data.empty:
        return None
    return data.iloc[0]

def format_money(value):
    if pd.isna(value):
        return "N/A"
    return f"${value / 1000:.2f} Billion"

def company_metric(company, metric, year):
    row = get_company_data(company, year)
    if row is None:
        return f"No data available for {company} in {year}."
    return f"📊 {company} ({year})\n\n{metric}\n\n{format_money(row[metric])}"

def company_report(company, year):
    row = get_company_data(company, year)
    if row is None:
        return f"No report available for {company} in {year}."
    return (
        f"# 📄 {company} Financial Report ({year})\n\n"
        f"**Revenue**\n{format_money(row['Revenue'])}\n\n"
        f"**Net Income**\n{format_money(row['Net Income'])}\n\n"
        f"**Assets**\n{format_money(row['Assets'])}\n\n"
        f"**Liabilities**\n{format_money(row['Liabilities'])}\n\n"
        f"**Operating Cash Flow**\n{format_money(row['Operating Cash Flow'])}"
    )

def financial_insight(company, year):
    row = get_company_data(company, year)
    if row is None:
        return f"No data available for {company} in {year}."
    insights = []
    if row["Revenue"] > 200000:
        insights.append("✅ Strong revenue generation.")
    if row["Net Income"] > 50000:
        insights.append("✅ High profitability.")
    if row["Assets"] > row["Liabilities"]:
        insights.append("✅ Assets exceed liabilities.")
    if row["Operating Cash Flow"] > row["Net Income"]:
        insights.append("✅ Strong operating cash flow.")
    if not insights:
        insights.append("Financial indicators are mixed.")
    return f"## 📈 {company} Financial Insight ({year})\n\n" + "\n".join(insights)

def highest_metric(metric, year):
    data = df[df["Year"] == year].dropna(subset=[metric])
    if data.empty:
        return f"No {metric} data is available for {year}."
    row = data.loc[data[metric].idxmax()]
    return f"🏆 Highest {metric} ({year})\n\n**Company:** {row['Company']}\n\n**Value:** {format_money(row[metric])}"

def lowest_metric(metric, year):
    data = df[df["Year"] == year].dropna(subset=[metric])
    if data.empty:
        return f"No {metric} data is available for {year}."
    row = data.loc[data[metric].idxmin()]
    return f"📉 Lowest {metric} ({year})\n\n**Company:** {row['Company']}\n\n**Value:** {format_money(row[metric])}"

def compare_metric(metric, year):
    data = df[df["Year"] == year].dropna(subset=[metric]).sort_values(metric, ascending=False)
    if data.empty:
        return f"No {metric} data is available for {year}."
    text = f"## 📊 {metric} Comparison ({year})\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (_, row) in enumerate(data.iterrows()):
        medal = medals[i] if i < 3 else "•"
        text += f"{medal} **{row['Company']}**\n{format_money(row[metric])}\n\n"
    return text + f"Leader: {data.iloc[0]['Company']}"

def trend_summary(company, metric):
    data = df[df["Company"].str.lower() == str(company).lower()].sort_values("Year")
    data = data.dropna(subset=[metric])
    if data.empty:
        return f"No {metric} trend data is available for {company}."
    lines = [f"{int(row['Year'])} → {format_money(row[metric])}" for _, row in data.iterrows()]
    start, end = data.iloc[0][metric], data.iloc[-1][metric]
    change = 0 if start == 0 else ((end - start) / abs(start)) * 100
    direction = "increased" if change >= 0 else "decreased"
    return (
        f"📈 {company} {metric} Trend\n\n"
        + "\n".join(lines)
        + f"\n\nOverall, {metric.lower()} has {direction} by {abs(change):.2f}% over the available period."
    )

HELP_TEXT = """
# 💹 Financial Analysis Chatbot

I currently support financial analysis for Microsoft, Apple and Tesla.

**Financial data**
- Tell me Apple's revenue
- Microsoft assets
- Tesla liabilities

**Reports**
- Apple report
- Tesla financial report
- Microsoft report

**Trends**
- Apple revenue trend
- Tesla operating cash flow trend

**Comparisons**
- Compare Microsoft and Apple revenue
- Compare operating cash flow
- Compare net income

**Rankings**
- Highest revenue
- Lowest liabilities
- Highest assets

**Definitions**
- What is revenue?
- Explain operating cash flow
- Define liabilities
"""

def financial_definition(metric):
    if metric is None:
        return "Please specify a financial term, such as revenue, net income, assets, liabilities, or operating cash flow."
    return financial_definitions.get(metric, "Definition not available.")

def chatbot_response(query):
    query = (query or "").strip()
    if not query:
        return "Please enter a question. Type **Help** to see examples."

    valid, message = validate_query(query)
    if not valid:
        return message

    parsed = parse_query(query)
    intent, companies = parsed["intent"], parsed["companies"]
    metric, year = parsed["metric"], parsed["year"]

    if intent == "help":
        return HELP_TEXT
    if intent == "definition":
        return financial_definition(metric)
    if intent == "highest":
        return highest_metric(metric, year)
    if intent == "lowest":
        return lowest_metric(metric, year)
    if intent == "compare":
        return compare_metric(metric, year)
    if not companies:
        return "Please mention Microsoft, Apple, or Tesla."
    if intent == "report":
        return company_report(companies[0], year)
    if intent in ["summary", "insight"]:
        return financial_insight(companies[0], year)
    if intent == "trend":
        return trend_summary(companies[0], metric)
    if metric is None:
        return "Please specify a financial metric, such as revenue, net income, assets, liabilities, or operating cash flow."
    return company_metric(companies[0], metric, year)

def financial_chat(message, history):
    return chatbot_response(message)

demo = gr.ChatInterface(
    fn=financial_chat,
    title="💹 Financial Analysis Chatbot",
    description=(
        "Analyze financial statements of Microsoft, Apple and Tesla "
        "(2023–2025). Features: financial reports, company comparison, "
        "revenue analysis, financial insights, trend analysis and definitions."
    ),
    examples=[
        "Tell me Apple's revenue",
        "Compare Microsoft and Apple revenue",
        "Highest revenue",
        "Apple report",
        "Tesla financial health",
        "Apple revenue trend",
        "What is operating cash flow?",
        "Help",
    ],
    theme="soft",
)

# Vercel detects this FastAPI ASGI application at the repository root.
app = FastAPI(title="Financial Analysis Chatbot")
app = gr.mount_gradio_app(app, demo, path="/")
