import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os

# --- Configuration ---
st.set_page_config(layout="wide", page_title="亚马逊宠物玩具竞品看板", initial_sidebar_state="expanded")
st.title("🐾 亚马逊宠物玩具竞品监控看板")
st.markdown("---")

# Data file path (已修正为 data.xlsx)
# 【重要提示】请将您的 CSV/Excel 文件重命名为 data.xlsx 并确保它与 app.py 在同一目录。
DATA_FILE = "data.xlsx"


# --- 1. Data Loading and Cleaning Function (Cached for speed) ---
@st.cache_data
def load_and_clean_data(file_path):
    # Error handling for missing file
    if not os.path.exists(file_path):
        # 修正提示：明确指出需要的是 data.xlsx
        st.error(
            f"Error: Could not find data file {file_path}. Please ensure it is named 'data.xlsx' and is in the same directory as app.py.")
        return pd.DataFrame()

    # 修正：使用 pd.read_excel 读取 Excel 文件
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        st.error(
            f"Error reading Excel file: {e}. Please ensure the file is a valid .xlsx file and you have installed 'openpyxl'.")
        return pd.DataFrame()

    # Function to clean and convert '评论数' (e.g., '3.4K' to 3400)
    def clean_reviews(review_str):
        if isinstance(review_str, str):
            review_str = review_str.strip()
            if 'K' in review_str or 'k' in review_str:
                try:
                    return float(review_str.upper().replace('K', '')) * 1000
                except ValueError:
                    return 0
            elif review_str.lower() in ('0', '无评论', '无', ''):
                return 0
            else:
                try:
                    # Direct conversion for numbers (e.g., '341')
                    return float(review_str.replace(',', ''))
                except ValueError:
                    return 0
        elif pd.api.types.is_numeric_dtype(review_str):  # 如果是数字类型（比如Excel直接存了数字）
            return review_str
        return 0

    df['评论数_数值'] = df['评论数'].apply(clean_reviews).astype(int)

    # Cleaning '等级' (Rating) and converting to numeric
    df['等级_数值'] = pd.to_numeric(df['等级'].replace(['无评分', '无', 'None', '无等级'], np.nan), errors='coerce')

    # Calculate Log10 for Y-axis visualization (smoothing large differences)
    df['评论数_Log10'] = np.log10(df['评论数_数值'] + 1)
    # Calculate bubble size (using sqrt of the raw review count for better visual scaling)
    df['气泡大小'] = np.sqrt(df['评论数_数值']) + 10

    # Drop rows where '等级' could not be determined
    df = df.dropna(subset=['等级_数值'])

    return df


# Load the data
df_original = load_and_clean_data(DATA_FILE)

if df_original.empty:
    st.stop()

# --- 2. Sidebar Interactive Filters ---
st.sidebar.header("🔍 数据筛选与分析")

# Rating Slider
min_rating_val = df_original['等级_数值'].min()
max_rating_val = df_original['等级_数值'].max()

min_rating_slider = st.sidebar.slider(
    "1. 筛选最低产品评分（等级）",
    min_rating_val,
    max_rating_val,
    min_rating_val,
    step=0.1
)

# Reviews Slider (Logarithmic Scale)
# Ensure max_log is not less than min_log
min_log_val = 0.0
max_log_val = float(df_original['评论数_Log10'].max())
if max_log_val < 1.0:  # Handle case where all reviews are very low
    max_log_val = 1.0

min_reviews_log = st.sidebar.slider(
    "2. 筛选最低评论数（热度）",
    min_log_val,
    max_log_val,
    1.0,  # Default starting point (10^1 = 10 reviews)
    step=0.1,
    format='评论数 > 10^%.1f'  # Display in scientific notation
)

# Filter the data based on user input
df_filtered = df_original[
    (df_original['等级_数值'] >= min_rating_slider) &
    (df_original['评论数_Log10'] >= min_reviews_log)  # FIX: Changed df_filtered to df_original
    ]

# Recalculate mean rating for KPI comparison
if not df_filtered.empty:
    avg_rating_filtered = df_filtered['等级_数值'].mean()
else:
    avg_rating_filtered = 0

# --- 3. Top Key Performance Indicators (KPIs) ---
st.header("📊 关键指标概览")
col1, col2, col3 = st.columns(3)

col1.metric(
    label="总商品数 (已筛选)",
    value=f"{len(df_filtered)} 条",
    delta=f"占总数的 {len(df_filtered) / len(df_original) * 100:.1f}%",
    delta_color="off"
)

col2.metric(
    label="平均产品评分",
    value=f"{avg_rating_filtered:.2f} 分",
    delta=f"原始平均: {df_original['等级_数值'].mean():.2f}",
    delta_color="off"
)

col3.metric(
    label="最高评论数",
    value=f"{df_filtered['评论数_数值'].max():,.0f} 条" if not df_filtered.empty else "N/A",
    delta="筛选集中的最高热度产品",
    delta_color="off"
)

st.markdown("---")

# --- 4. Core Chart: Rating vs. Popularity Bubble Chart (Interactive) ---
st.header("⭐ 评分与热度（评论数）关系气泡图")
st.markdown("💡 气泡越大 = 热度越高；颜色越亮 = 评分越高。鼠标悬停可查看标题。")

if df_filtered.empty:
    st.warning("根据当前筛选条件，没有找到符合要求的商品。请调整侧边栏的滑块。")
else:
    # Use Plotly Express to create the interactive bubble chart
    fig_bubble = px.scatter(
        df_filtered,
        x='等级_数值',
        y='评论数_Log10',
        size='气泡大小',
        color='等级_数值',
        hover_name='标题',
        title='产品热度与质量分布（气泡图）',
        labels={'等级_数值': '产品评分（等级）', '评论数_Log10': '产品热度（评论数, Log10）'},
        color_continuous_scale=px.colors.sequential.Viridis
    )

    # Customize the layout for better readability
    fig_bubble.update_layout(
        xaxis_title="产品评分 (等级)",
        yaxis_title="产品热度 (评论数)",
        # Define Y-axis ticks to show actual magnitude (10, 100, 1K, 10K)
        yaxis=dict(tickvals=[1, 2, 3, 4, 5], ticktext=['10', '100', '1K', '10K', '100K']),
        # Set X-axis range to focus on the typical rating zone
        xaxis=dict(tick0=4.0, dtick=0.1, range=[3.8, 5.0]),
        height=550,
        hoverlabel=dict(bgcolor="white", font_size=12)  # Improve hover box appearance
    )

    st.plotly_chart(fig_bubble, use_container_width=True)

# --- 5. Bottom Table ---
st.header("📋 筛选后的原始数据表")
st.markdown(f"**当前显示 {len(df_filtered)} 条数据。**")

st.dataframe(
    df_filtered[['标题', '等级_数值', '评论数_数值']],
    use_container_width=True,
    column_config={
        "等级_数值": st.column_config.NumberColumn("等级 (评分)", format="%.2f"),
        "评论数_数值": st.column_config.NumberColumn("评论数 (数值)", format="%d"),
        "标题": st.column_config.TextColumn("标题", help="亚马逊产品标题")
    }
)