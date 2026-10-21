import html
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="철도 설비 분석 대시보드", page_icon="🚆", layout="wide")

CSV_PATH = "/content/drive/MyDrive/데이터분석/analysis_result.csv"
REQUIRED_COLUMNS = [
    "설비ID", "측정시각", "온도_C", "AI결과",
    "목표시각", "다음온도_C", "AI예측온도_C",
]


@st.cache_data

def load_data(path):
    data = pd.read_csv(path, encoding="utf-8-sig")
    data.columns = data.columns.str.strip()
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in data.columns]
    if missing_columns:
        raise ValueError("필수 열 누락: " + ", ".join(missing_columns))

    data["설비ID"] = data["설비ID"].astype("string").str.strip().replace("", pd.NA)
    data["AI결과"] = data["AI결과"].astype("string").str.strip().replace("", pd.NA)
    data["측정시각"] = pd.to_datetime(data["측정시각"], errors="coerce")
    data["목표시각"] = pd.to_datetime(data["목표시각"], errors="coerce")
    for col in ["온도_C", "다음온도_C", "AI예측온도_C"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    excluded_rows = int(data["측정시각"].isna().sum() + (
        data["측정시각"].notna() & data["설비ID"].isna()
    ).sum())
    data = data.dropna(subset=["설비ID", "측정시각"]).copy()
    return data.sort_values("측정시각"), excluded_rows


st.title("🚆 철도 설비 분석 대시보드")
st.caption("교육용 가상 자료 · AI '확인후보'는 고장 확정이 아니며 담당자 검토가 필요합니다.")

try:
    df, excluded_rows = load_data(CSV_PATH)
except (FileNotFoundError, OSError, ValueError, pd.errors.ParserError) as exc:
    st.error(f"데이터를 불러올 수 없습니다: {exc}")
    st.stop()

if df.empty:
    st.warning("분석할 수 있는 유효한 데이터가 없습니다. CSV 파일을 확인하세요.")
    st.stop()

with st.sidebar:
    st.header("🔎 조회 조건")
    equipment = st.selectbox("설비 선택", sorted(df["설비ID"].unique().tolist()))
    equipment_df = df.loc[df["설비ID"] == equipment].copy()
    first_date = equipment_df["측정시각"].min().date()
    last_date = equipment_df["측정시각"].max().date()
    start = st.date_input(
        "시작일", value=first_date, min_value=first_date, max_value=last_date,
        key=f"start_{equipment}",
    )
    end = st.date_input(
        "종료일", value=last_date, min_value=first_date, max_value=last_date,
        key=f"end_{equipment}",
    )
    st.caption("조건을 바꾸면 모든 탭과 보고서가 자동으로 갱신됩니다.")

if start > end:
    st.error("시작일이 종료일보다 늦습니다. 조회 기간을 다시 선택하세요.")
    st.stop()

view = equipment_df.loc[
    (equipment_df["측정시각"].dt.date >= start)
    & (equipment_df["측정시각"].dt.date <= end)
].copy()
candidates = view.loc[view["AI결과"].eq("확인후보").fillna(False)].copy()
pred = view.dropna(subset=["다음온도_C", "AI예측온도_C"]).copy()
pred["예측차이_C"] = (pred["다음온도_C"] - pred["AI예측온도_C"]).abs()

count = len(view)
candidate_count = len(candidates)
ratio = candidate_count / count * 100 if count else None
mae = pred["예측차이_C"].mean() if len(pred) else None
average_temp = view["온도_C"].mean() if count else None
max_temp = view["온도_C"].max() if count else None
missing_temp = int(view["온도_C"].isna().sum())
missing_ai = int(view["AI결과"].isna().sum())
repeated_time = int(view.duplicated(subset=["설비ID", "측정시각"]).sum())
quality_count = missing_temp + missing_ai + repeated_time

ratio_text = f"{ratio:.1f}%" if ratio is not None else "계산 불가"
mae_text = f"{mae:.2f}℃" if mae is not None else "비교 자료 없음"
avg_text = f"{average_temp:.1f}℃" if pd.notna(average_temp) else "자료 없음"
max_text = f"{max_temp:.1f}℃" if pd.notna(max_temp) else "자료 없음"
period_text = f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d}"

if count == 0:
    status = "조회 자료 없음"
    conclusion = "선택한 기간에 측정 자료가 없습니다. 날짜를 바꾼 뒤 다시 확인해야 합니다."
elif candidate_count:
    status = "담당자 검토 권장"
    conclusion = (
        f"총 {count:,}건 중 {candidate_count:,}건({ratio_text})이 AI 확인후보로 표시되었습니다. "
        "고장 확정은 아니며, 해당 시각의 센서값과 운전 상태를 확인하는 것이 좋습니다."
    )
elif quality_count:
    status = "데이터 확인 권장"
    conclusion = (
        f"총 {count:,}건 중 AI 확인후보는 없었지만, 누락값 또는 중복 시각 등 "
        "점검할 데이터가 있습니다. 고장이 없다고 단정할 수는 없습니다."
    )
else:
    status = "AI 확인후보 없음"
    conclusion = (
        f"총 {count:,}건에서 AI 확인후보는 발견되지 않았습니다. "
        "이는 설비가 정상이라고 확정하는 결과가 아니므로 정기 점검은 유지해야 합니다."
    )

forecast_explanation = (
    f"실제 다음 온도와 AI 예측값 {len(pred):,}건을 비교한 결과, "
    f"평균 차이는 {mae:.2f}℃였습니다. 수치가 낮을수록 두 값이 가깝다는 뜻이지만, "
    "별도의 허용 기준 없이 예측 성능을 합격/불합격으로 판단할 수 없습니다."
    if mae is not None
    else "실제값과 예측값이 모두 있는 자료가 없어 평균 예측 차이를 계산할 수 없습니다."
)

if count == 0:
    actions = [
        "조회 기간과 설비 선택이 맞는지 확인합니다.",
        "원본 CSV에 해당 기간의 측정 자료가 있는지 확인합니다.",
        "자료가 확보된 후 AI 분석 결과를 다시 검토합니다.",
    ]
else:
    actions = [
        (
            "AI 확인후보가 표시된 시각의 센서값, 운전 조건, 정비 이력을 확인합니다."
            if candidate_count else
            "AI 확인후보는 없지만 기존 정기점검 및 현장 확인 절차를 유지합니다."
        ),
        (
            "온도·AI 결과의 빈 값과 같은 시각의 중복 기록을 확인합니다."
            if quality_count else
            "데이터 누락과 기록 상태를 정기적으로 점검합니다."
        ),
        (
            "예측값과 실제값의 차이가 큰 시각부터 측정 조건을 살펴봅니다."
            if len(pred) else
            "실제 다음 온도와 AI 예측값을 확보해 예측 결과를 검증합니다."
        ),
    ]

# 탭은 화면을 나누지만, Streamlit은 각 탭의 코드도 실행합니다.
tab1, tab2, tab3, tab4 = st.tabs([
    "1. 조회 결과", "2. AI 점검 후보", "3. 다음 1시간 온도 예측", "4. 업무 검토 및 저장",
])

with tab1:
    st.subheader("조회 결과")
    c1, c2, c3 = st.columns(3)
    c1.metric("측정 자료", f"{count:,}건")
    c2.metric("평균 온도", avg_text)
    c3.metric("최고 온도", max_text)
    if count:
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.caption("평균/최고 온도는 선택된 기간의 측정값이며, 정상·비정상 판정 기준이 아닙니다.")
    else:
        st.info("조회된 자료가 없습니다. 사이드바의 기간을 변경하세요.")

with tab2:
    st.subheader("AI 점검 후보")
    c1, c2 = st.columns(2)
    c1.metric("확인후보", f"{candidate_count:,}건")
    c2.metric("전체 대비 비율", ratio_text)
    st.caption("확인후보 = AI가 추가 확인을 제안한 기록 · 실제 고장 여부는 현장 확인이 필요합니다.")

    if count:
        counts = (view["AI결과"].fillna("미분류")
                  .value_counts().rename_axis("AI 결과").reset_index(name="건수"))
        st.dataframe(counts, use_container_width=True, hide_index=True)
        temperature_view = view.dropna(subset=["온도_C"])
        if not temperature_view.empty:
            fig = px.line(temperature_view, x="측정시각", y="온도_C", title="온도 변화와 AI 확인후보")
            marks = candidates.dropna(subset=["온도_C"])
            fig.add_scatter(
                x=marks["측정시각"], y=marks["온도_C"], mode="markers",
                name="AI 확인후보", marker=dict(color="red", size=9),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("온도 측정값이 없어 추이 그래프를 표시할 수 없습니다.")
        st.markdown("**추가 확인이 필요한 기록**")
        if candidate_count:
            st.dataframe(candidates, use_container_width=True, hide_index=True)
        else:
            st.info("선택한 기간에는 AI 확인후보가 없습니다.")
    else:
        st.info("조회된 자료가 없습니다.")

with tab3:
    st.subheader("다음 1시간 온도 예측")
    c1, c2 = st.columns(2)
    c1.metric("평균 예측 차이(MAE)", mae_text)
    c2.metric("비교한 자료", f"{len(pred):,}건")
    st.info("평균 예측 차이: AI가 예측한 온도와 실제 온도가 평균적으로 몇 ℃ 다른지 보여줍니다. 작은 값일수록 가깝습니다.")
    if len(pred):
        chart_data = pred.dropna(subset=["목표시각"]).sort_values("목표시각")
        if not chart_data.empty:
            fig2 = px.line(
                chart_data, x="목표시각", y=["다음온도_C", "AI예측온도_C"],
                title="실제 온도와 AI 예측 온도 비교",
                labels={"value": "온도(℃)", "variable": "구분"},
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning("목표시각 정보가 없어 그래프를 표시할 수 없습니다.")
        st.markdown("**예측 차이가 큰 기록 5건**")
        st.dataframe(
            pred.nlargest(5, "예측차이_C")[[
                "측정시각", "목표시각", "다음온도_C", "AI예측온도_C", "예측차이_C",
            ]],
            use_container_width=True,
            hide_index=True,
        )
        st.caption("허용 오차 기준이 제공되지 않아 예측 결과를 좋음·나쁨으로 단정하지 않습니다.")
    else:
        st.warning("실제 온도와 AI 예측 온도가 모두 있는 비교 자료가 없습니다.")

with tab4:
    st.subheader("📄 철도 설비 점검 요약 보고서")
    st.caption("핵심 결과 → 쉬운 해석 → 권장 조치 순서로 읽는 요약 보고서")
    st.write(f"**설비:** {equipment}　 | 　**기간:** {period_text}　 | 　**종합 안내:** {status}")

    c1, c2, c3 = st.columns(3)
    c1.metric("① 측정 건수", f"{count:,}건")
    c2.metric("② AI 확인후보", f"{candidate_count:,}건 ({ratio_text})")
    c3.metric("③ 평균 예측 차이", mae_text)

    st.markdown("#### 한 줄 결론")
    st.info(conclusion)

    st.markdown("#### 예측 결과는 이렇게 이해하세요")
    st.write(forecast_explanation)

    st.markdown("#### 담당자 권장 조치")
    for i, action in enumerate(actions, start=1):
        st.write(f"{i}. {action}")

    with st.expander("데이터 상태 및 용어 설명 (자세히 보기)"):
        st.write(f"온도 누락: {missing_temp:,}건 · AI 결과 누락: {missing_ai:,}건 · 같은 시각의 기록 중복: {repeated_time:,}건")
        if excluded_rows:
            st.warning(f"전체 원본에서 설비ID 또는 측정시각이 없어 제외한 기록: {excluded_rows:,}건 (현재 설비·기간 기준이 아님)")
        st.write("**AI 확인후보:** AI가 추가 확인을 권한 기록이며 고장을 뜻하지 않습니다.")
        st.write("**MAE:** 실제 온도와 예측 온도 차이의 절댓값을 평균낸 수치입니다.")
        st.write("**중복 시각:** 같은 설비와 시각에 여러 기록이 있는 경우로, 반드시 오류라는 의미는 아닙니다.")

    note = st.text_area(
        "담당자 검토 의견",
        "센서 상태와 운전 조건을 확인한 뒤 현장 담당자가 점검 필요 여부를 판단합니다.",
        height=100,
    )
    st.caption("안내: 이 보고서는 교육용 데이터 기반 참고자료이며, 고장 확정이나 안전 판정을 대신할 수 없습니다.")

    report_date = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
    quality_summary = (
        f"온도 누락 {missing_temp:,}건 / AI 결과 누락 {missing_ai:,}건 / 같은 시각의 중복 {repeated_time:,}건"
    )
    report_text = "\n".join([
        "철도 설비 점검 요약 보고서",
        f"작성 시각: {report_date}",
        f"대상 설비: {equipment}",
        f"조회 기간: {period_text}",
        f"종합 안내: {status}",
        "",
        "1. 핵심 결과",
        f"- 측정 자료: {count:,}건",
        f"- AI 확인후보: {candidate_count:,}건 (전체 대비 {ratio_text})",
        f"- 평균 온도: {avg_text} / 최고 온도: {max_text}",
        f"- 예측 평균 차이(MAE): {mae_text} (비교 {len(pred):,}건)",
        "",
        "2. 한 줄 결론",
        conclusion,
        "",
        "3. 예측 결과 해석",
        forecast_explanation,
        "",
        "4. 담당자 권장 조치",
        *(f"{i}. {item}" for i, item in enumerate(actions, start=1)),
        "",
        "5. 데이터 확인 사항",
        quality_summary,
        f"원본 전체 제외 기록: {excluded_rows:,}건 (설비ID·측정시각 누락)",
        "",
        "6. 담당자 검토 의견",
        note.strip() or "(미작성)",
        "",
        "※ 교육용 가상 자료입니다. AI 확인후보는 고장 확정이 아니며 이 결과는 안전 판정을 대신하지 않습니다.",
    ])

    def safe(value):
        return html.escape(str(value))

    actions_html = "".join(f"<li>{safe(action)}</li>" for action in actions)
    html_report = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>철도 설비 점검 요약 보고서</title>
<style>
body {{font-family: Arial, 'Malgun Gothic', sans-serif; color:#17253a; line-height:1.65; max-width:820px; margin:42px auto; padding:0 22px;}}
h1 {{font-size:25px; border-bottom:3px solid #194f7b; padding-bottom:12px;}}
h2 {{font-size:17px; color:#194f7b; margin-top:25px;}}
.meta {{color:#536274; font-size:13px;}} .stats {{display:flex; gap:12px; flex-wrap:wrap;}}
.stat {{border:1px solid #d5dee8; border-radius:9px; padding:12px 16px; flex:1; min-width:150px;}}
.stat b {{font-size:20px; display:block;}} .note {{background:#f0f5fa; padding:13px 16px; border-radius:8px;}}
small {{color:#596779;}} pre {{font:inherit; white-space:pre-wrap; word-break:break-word;}}
@media print {{body {{margin:15mm auto;}} .stat {{break-inside:avoid;}}}}
</style></head><body>
<h1>철도 설비 점검 요약 보고서</h1>
<p class="meta">작성: {safe(report_date)} | 설비: {safe(equipment)} | 기간: {safe(period_text)}</p>
<p><strong>종합 안내:</strong> {safe(status)}</p>
<div class="stats"><div class="stat">측정 자료<b>{count:,}건</b></div>
<div class="stat">AI 확인후보<b>{candidate_count:,}건 ({safe(ratio_text)})</b></div>
<div class="stat">예측 평균 차이<b>{safe(mae_text)}</b></div></div>
<h2>1. 한 줄 결론</h2><p class="note">{safe(conclusion)}</p>
<h2>2. 측정 및 예측 결과</h2><p>평균 온도: {safe(avg_text)} / 최고 온도: {safe(max_text)}<br>
{safe(forecast_explanation)}</p>
<h2>3. 담당자 권장 조치</h2><ol>{actions_html}</ol>
<h2>4. 데이터 확인 사항</h2><p>{safe(quality_summary)}<br>
원본 전체 제외 기록: {excluded_rows:,}건 (설비ID·측정시각 누락)</p>
<h2>5. 담당자 검토 의견</h2><pre>{safe(note.strip() or '(미작성)')}</pre>
<hr><small>교육용 가상 자료입니다. AI 확인후보는 고장 확정이 아니며, 이 보고서는 안전 판정을 대신하지 않습니다.</small>
</body></html>"""

    st.markdown("#### 보고서 및 데이터 저장")
    d1, d2, d3, d4 = st.columns(4)
    d1.download_button("보고서 HTML", html_report.encode("utf-8-sig"), "railway_report.html", "text/html", use_container_width=True)
    d2.download_button("보고서 TXT", report_text.encode("utf-8-sig"), "railway_report.txt", "text/plain", use_container_width=True)
    d3.download_button("조회 결과 CSV", view.to_csv(index=False).encode("utf-8-sig"), "dashboard_result.csv", "text/csv", use_container_width=True)
    d4.download_button("확인후보 CSV", candidates.to_csv(index=False).encode("utf-8-sig"), "inspection_candidates.csv", "text/csv", use_container_width=True)
    st.caption("HTML 보고서를 웹브라우저에서 연 뒤 인쇄 → PDF로 저장할 수 있습니다.")
