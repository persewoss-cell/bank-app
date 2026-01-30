import streamlit as st
import pandas as pd
import requests

WEBAPP_URL = "https://script.google.com/macros/s/AKfycbx4aS0JiOp-P2_AO5uh_vTbkXzDXzLiDa067a9cr7o/dev"  # /exec 로 끝나는 URL 그대로

st.set_page_config(page_title="학생 포인트 통장", layout="wide")
st.title("🏦 학생 포인트 통장 (구글시트 연동)")

# -------------------------
# 1) 입력 영역
# -------------------------
col1, col2 = st.columns([2, 3])

with col1:
    name = st.text_input("통장 이름(학생 이름)")
with col2:
    memo = st.text_input("내역(예: 숙제완료, 발표참여 등)")

c1, c2, c3 = st.columns(3)
with c1:
    deposit = st.number_input("입금(포인트)", min_value=0, step=1, value=0)
with c2:
    withdraw = st.number_input("출금(포인트)", min_value=0, step=1, value=0)
with c3:
    st.write("")  # 여백
    st.write("")

if st.button("통장에 기록하기(저장)"):
    if not name.strip():
        st.error("이름을 입력해 주세요.")
    elif not memo.strip():
        st.error("내역을 입력해 주세요.")
    elif deposit > 0 and withdraw > 0:
        st.error("입금/출금은 둘 중 하나만 입력해 주세요.")
    elif deposit == 0 and withdraw == 0:
        st.error("입금 또는 출금 중 하나는 입력해 주세요.")
    else:
        payload = {
            "name": name.strip(),
            "memo": memo.strip(),
            "deposit": int(deposit),
            "withdraw": int(withdraw),
        }
        try:
            r = requests.post(WEBAPP_URL, json=payload, timeout=10)
            st.success("저장 완료! 아래 통장 내역을 확인하세요.")
            st.rerun()
        except Exception as e:
            st.error("저장 실패")
            st.write(e)

st.divider()

# -------------------------
# 2) 통장 내역 불러오기(읽기)
# -------------------------
st.subheader("📒 통장 내역")

try:
    resp = requests.get(WEBAPP_URL, timeout=10)  # doGet으로 전체 표 받음
    values = resp.json()  # 2차원 배열 (헤더 포함)
except Exception as e:
    st.error("구글시트에서 내역을 불러오지 못했어요. (doGet 추가/재배포 확인)")
    st.write(e)
    st.stop()

if not values or len(values) < 2:
    st.info("아직 기록이 없어요. 위에서 첫 기록을 추가해 보세요.")
    st.stop()

# 첫 행은 헤더라고 가정
headers = values[0]
rows = values[1:]

df = pd.DataFrame(rows, columns=headers)

# ---- 여기부터 '통장처럼' 정리 ----
# 날짜열 이름이 정확히 '날짜시간'이 아니라면, 1열이 날짜라고 가정
# (Apps Script가 new Date()를 넣으면 첫 칸이 날짜시간이 됨)
date_col = df.columns[0]
name_col = df.columns[1]
memo_col = df.columns[2]
dep_col = df.columns[3]
wd_col = df.columns[4]

# 숫자형 변환
df[dep_col] = pd.to_numeric(df[dep_col], errors="coerce").fillna(0).astype(int)
df[wd_col]  = pd.to_numeric(df[wd_col], errors="coerce").fillna(0).astype(int)

# 학생 필터(이름별 통장)
if name.strip():
    df2 = df[df[name_col] == name.strip()].copy()
else:
    df2 = df.copy()

if df2.empty:
    st.warning("해당 이름으로 저장된 기록이 없어요. 이름을 확인해 주세요.")
    st.stop()

# 총액 계산(입금-출금 누적)
df2["변동"] = df2[dep_col] - df2[wd_col]
df2["총액"] = df2["변동"].cumsum()

# 표 출력(통장형)
bank_view = df2[[date_col, memo_col, dep_col, wd_col, "총액"]].rename(
    columns={
        date_col: "날짜-시간",
        memo_col: "내역",
        dep_col: "입금",
        wd_col: "출금",
    }
)

st.write(f"현재 총액: **{int(bank_view['총액'].iloc[-1])} 포인트**")
st.dataframe(bank_view, use_container_width=True, hide_index=True)
