import streamlit as st
import snowflake.connector
import pandas as pd
import re

# ── CONFIG ──
st.set_page_config(
    page_title="PharmaSignal AI Agent",
    page_icon="💊",
    layout="wide"
)

# ── CONEXIÓN SNOWFLAKE ──
@st.cache_resource
def get_connection():
    return snowflake.connector.connect(
        user=st.secrets["snowflake"]["user"],
        password=st.secrets["snowflake"]["password"],
        account=st.secrets["snowflake"]["account"],
        warehouse=st.secrets["snowflake"]["warehouse"],
        database="PHARMASIGNAL",
        schema="RAW"
    )

def run_query(sql):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql)
    df = pd.DataFrame(cursor.fetchall(),
                      columns=[d[0] for d in cursor.description])
    return df

# ── SCHEMA ──
SCHEMA_CONTEXT = """
You are a Snowflake SQL expert for a pharmacovigilance database.
Generate ONE single valid Snowflake SQL query. No explanation, no markdown, no backticks, no semicolons.

Tables:

PHARMASIGNAL.RAW.RAW_DRUGS (alias: D)
- DRUG_ID VARCHAR
- DRUG_NAME VARCHAR
- THERAPEUTIC_AREA VARCHAR (values: 'Oncology', 'Cardiology', 'CNS', 'Autoimmune')
- INDICATION VARCHAR
- LAUNCH_DATE DATE
- CLASS_AVG_SERIOUS_RATE FLOAT

PHARMASIGNAL.RAW.RAW_ADVERSE_EVENTS (alias: AE)
- REPORT_ID VARCHAR
- DRUG_ID VARCHAR
- DRUG_NAME VARCHAR
- THERAPEUTIC_AREA VARCHAR
- EVENT_DATE DATE
- QUARTER VARCHAR
- MONTHS_ON_MARKET INTEGER
- REACTION VARCHAR
- IS_NOVEL_REACTION VARCHAR (1=novel, 0=not novel)
- OUTCOME VARCHAR (values: 'Death', 'Hospitalization', 'Disability', 'Moderate', 'Non-serious')
- IS_SERIOUS VARCHAR (1=serious, 0=not serious)
- REPORTER_TYPE VARCHAR
- COUNTRY VARCHAR
- AGE_GROUP VARCHAR
- SEX VARCHAR

PHARMASIGNAL.RAW.RAW_SALES_VOLUME (alias: S)
- DRUG_ID VARCHAR
- YEAR_MONTH VARCHAR
- UNITS_SOLD INTEGER

Rules:
- Use alias D for RAW_DRUGS, AE for RAW_ADVERSE_EVENTS, S for RAW_SALES_VOLUME
- Every column must be prefixed with its table alias
- Every non-aggregated column in SELECT must be in GROUP BY
- JOIN tables using DRUG_ID
- Return only ONE SQL query, no semicolons
- To filter by year, use YEAR(column) = 2024 instead of DATE_TRUNC
"""

def clean_sql(sql):
    sql = sql.replace('```sql', '').replace('```', '').strip()
    # Eliminar comentarios
    sql = re.sub(r'--.*', '', sql)
    # Eliminar backslashes
    sql = sql.replace('\\_', '_')
    # Tomar solo primera query
    if ';' in sql:
        sql = sql.split(';')[0].strip()
    # Añadir schema completo si falta
    sql = re.sub(r'\bFROM\s+D\b', 'FROM PHARMASIGNAL.RAW.RAW_DRUGS D', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bJOIN\s+AE\b', 'JOIN PHARMASIGNAL.RAW.RAW_ADVERSE_EVENTS AE', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bJOIN\s+S\b', 'JOIN PHARMASIGNAL.RAW.RAW_SALES_VOLUME S', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bFROM\s+AE\b', 'FROM PHARMASIGNAL.RAW.RAW_ADVERSE_EVENTS AE', sql, flags=re.IGNORECASE)
    return sql

def generate_sql(user_question):
    prompt = f"{SCHEMA_CONTEXT}\n\nUser question: {user_question}\n\nSQL query:"
    
    sql = f"""
    SELECT SNOWFLAKE.CORTEX.COMPLETE(
        'llama3-8b',
        '{prompt.replace("'", "''")}'
    ) AS generated_sql
    """
    result = run_query(sql)
    return clean_sql(result['GENERATED_SQL'][0].strip())


def summarize_results(user_question, df):
    data_str = df.to_string(index=False, max_rows=20)
    prompt = f"""You are a pharmacovigilance analyst. 
The user asked: {user_question}

The data returned is:
{data_str}

Provide a clear, concise answer in 2-3 sentences. 
Focus on the key insight. Be specific with numbers."""

    sql = f"""
    SELECT SNOWFLAKE.CORTEX.COMPLETE(
        'llama3-8b',
        '{prompt.replace("'", "''")}'
    ) AS summary
    """
    result = run_query(sql)
    return result['SUMMARY'][0].strip()

# ── UI ──
st.title("💊 PharmaSignal AI Agent")
st.caption("Ask questions about drug safety data in natural language")

# Sidebar con ejemplos
with st.sidebar:
    st.header("Example questions")
    examples = [
        "Which drug has the most severe adverse events?",
        "How many fatal outcomes has Veraximab had?",
        "What are the most common reactions for Oncology drugs?",
        "Which drug has the highest number of reports in 2024?",
        "Compare serious adverse events between Cardiology and CNS drugs"
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state.question = ex

# Input
question = st.text_input(
    "Your question:",
    value=st.session_state.get("question", ""),
    placeholder="e.g. Which drug has the most adverse events?"
)

if st.button("Ask", type="primary") and question:
    with st.spinner("Generating SQL..."):
        try:
            # Paso 1: generar SQL
            generated_sql = generate_sql(question)
            
            with st.expander("Generated SQL", expanded=False):
                st.code(generated_sql, language="sql")
            
            # Paso 2: ejecutar SQL
            with st.spinner("Running query..."):
                df = run_query(generated_sql)
            
            # Paso 3: mostrar datos
            st.subheader("Results")
            st.dataframe(df, use_container_width=True)
            
            # Paso 4: resumen en lenguaje natural
            with st.spinner("Summarizing..."):
                summary = summarize_results(question, df)
            
            st.info(f"💡 {summary}")
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.caption("The SQL generated may need adjustment. Try rephrasing your question.")

# Historial en session state
if "history" not in st.session_state:
    st.session_state.history = []