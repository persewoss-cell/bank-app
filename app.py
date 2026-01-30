import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone, timedelta

# ✅ 너의 구글 Apps Script 웹앱 URL (/exec 로 끝나는 주소)
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzwbS_dIJGHTe4oyNK9QMWm0CXqqjgMJ3p-q0MQANqZ0mUQhrHPOIHVSgcH41vrLep-/exec"

st.set_page_config(page_title="학생 포인트 통장", layout="wide")
st.title("🏦 학생 포인트 통장")

# -------------------------
# 날짜시간 한국식 포맷 변환
# yyyy년 mm월 dd일 오전/오후 00시 00분
# -------------------------
KST = timezone(timedelta(hours=9))

def format_kr_datetime(val) -> str:
    if val is None or val == "":
        return ""

    if isinstance(val, datetime):
        dt = val
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        else:
            dt = dt.astimezone(KST)
    else:
        s = str(val).strip()
        try:
            # 예: 2026-01-30T13:35:02.000Z
            if "T" in s and s.endswith("Z"):
                dt = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(KST)
            else:
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=KST)
                else:
                    dt = dt.astimezone(KST)
        except Exception:
            return s  # 파싱 실패 시 원문

    ampm = "오전" if dt.hour < 12 else "오후"
    hour12 = dt.hour % 12
    if hour12 == 0:
        hour12 = 12

    return f"{dt.year}년 {dt.month:02d}월 {dt.day:02d}일 {ampm} {hour12:02d}시 {dt.minute:02d}분"


# -------------------------
# API helpers
# -------------------------
def api_list_accounts():
    r = requests.get(WEBAPP_URL, params={"action": "list_accounts"}, timeout=10)
    return r.json()

def api_create_account(name, pin):
    r = requests.post(WEBAPP_URL, json={"action": "create_account", "name": name, "pin": pin}, timeout=10)
    return r.json()

def api_delete_account(name, pin):
    r = requests.post(WEBAPP_URL, json={"action": "delete_account", "name": name, "pin": pin}, timeout=10)
    return r.json()

def api_add_tx(name, pin, memo, deposit, withdraw):
    r = requests.post(
        WEBAPP_URL,
        json={
            "action": "add_transaction",
            "name": name,
            "pin": pin,
            "memo": memo,
            "deposit": int(deposit),
            "withdraw": int(withdraw),
        },
        timeout=10,
    )
    return r.json()

def api_get_txs(name, pin):
    r = requests.get(WEBAPP_URL, params={"action": "get_transactions", "name": name, "pin": pin}, timeout=10)
    return r.json()

def pin_ok(pin: str) -> bool:
    return pin.isdigit() and len(pin) == 4


# -------------------------
# Sidebar: account creation + deletion
# -------------------------
if "delete_confirm" not in st.session_state:
    st.session_state.delete_confirm = False

with st.sidebar:
    st.header("➕ 계정 만들기")
    st.caption("이름 + 4자리 비밀번호로 계정을 만들면, 구글시트에 그 이름 탭이 자동 생성됩니다.")

    new_name = st.text_input("이름(계정)", key="new_name").strip()
    new_pin = st.text_input("비밀번호(4자리 숫자)", type="password", key="new_pin").strip()

    cbtn1, cbtn2 = st.columns(2)

    with cbtn1:
        if st.button("계정 생성"):
            if not new_name:
                st.error("이름을 입력해 주세요.")
            elif not pin_ok(new_pin):
                st.error("비밀번호는 4자리 숫자여야 해요. (예: 0123)")
            else:
                res = api_create_account(new_name, new_pin)
                if res.get("ok"):
                    st.success("계정 생성 완료! 상단 탭에서 계정을 선택하세요.")
                    st.session_state.delete_confirm = False
                    st.rerun()
                else:
                    st.error(res.get("error", "계정 생성 실패"))

    with cbtn2:
        if st.button("삭제"):
            # 삭제 버튼 누르면 확인 단계로 진입
            st.session_state.delete_confirm = True

    # 확인 UI (팝업 대신 확인 영역)
    if st.session_state.delete_confirm:
        st.warning("정말로 삭제하시겠습니까?")
        st.caption("※ 삭제하면 해당 계정 탭(통장 내역)도 함께 삭제됩니다.")

        y, n = st.columns(2)
        with y:
            if st.button("예", key="delete_yes"):
                if not new_name:
                    st.error("삭제할 이름(계정)을 입력해 주세요.")
                elif not pin_ok(new_pin):
                    st.error("비밀번호는 4자리 숫자여야 해요. (예: 0123)")
                else:
                    res = api_delete_account(new_name, new_pin)
                    if res.get("ok"):
                        st.success("삭제 완료!")
                        st.session_state.delete_confirm = False
                        # 입력칸도 비워주기(선택)
                        st.session_state.new_name = ""
                        st.session_state.new_pin = ""
                        st.rerun()
                    else:
                        st.error(res.get("error", "삭제 실패"))

        with n:
            if st.button("아니오", key="delete_no"):
                st.session_state.delete_confirm = False
                st.rerun()


# -------------------------
# Load accounts
# -------------------------
accounts_res = api_list_accounts()
if not accounts_res.get("ok"):
    st.error(accounts_res.get("error", "계정 목록을 불러오지 못했어요."))
    st.stop()

accounts = accounts_res.get("accounts", [])
if not accounts:
    st.info("아직 계정이 없어요. 왼쪽(사이드바)에서 계정을 먼저 만들어 주세요.")
    st.stop()


# -------------------------
# Top Tabs: select account like browser tabs
# -------------------------
st.subheader("👤 계정 탭(인터넷 탭처럼 선택)")
tabs = st.tabs(accounts)

for idx, tab in enumerate(tabs):
    name = accounts[idx]

    with tab:
        st.markdown(f"### ✅ 현재 선택: **{name}**")

        pin = st.text_input(
            "비밀번호(4자리) 입력(조회/저장용)",
            type="password",
            key=f"pin_{name}"
        ).strip()

        st.divider()

        # 거래 기록
        st.subheader("📝 거래 기록(통장에 찍기)")
        memo = st.text_input("내역", key=f"memo_{name}").strip()

        c1, c2 = st.columns(2)
        with c1:
            deposit = st.number_input("입금", min_value=0, step=1, value=0, key=f"dep_{name}")
        with c2:
            withdraw = st.number_input("출금", min_value=0, step=1, value=0, key=f"wd_{name}")

        if st.button("통장에 기록하기(저장)", key=f"save_{name}"):
            if not pin_ok(pin):
                st.error("비밀번호(4자리 숫자)를 입력해 주세요.")
            elif not memo:
                st.error("내역을 입력해 주세요.")
            elif (deposit > 0 and withdraw > 0) or (deposit == 0 and withdraw == 0):
                st.error("입금/출금은 둘 중 하나만 입력해 주세요.")
            else:
                res = api_add_tx(name, pin, memo, deposit, withdraw)
                if res.get("ok"):
                    st.success("저장 완료!")
                    st.rerun()
                else:
                    st.error(res.get("error", "저장 실패"))

        st.divider()

        # 통장 내역
        st.subheader("📒 통장 내역")

        if not pin_ok(pin):
            st.info("통장 내역을 보려면 비밀번호(4자리 숫자)를 입력해 주세요.")
            continue

        tx_res = api_get_txs(name, pin)
        if not tx_res.get("ok"):
            st.error(tx_res.get("error", "내역을 불러오지 못했어요."))
            continue

        headers = tx_res.get("headers", ["datetime", "memo", "deposit", "withdraw"])
        rows = tx_res.get("rows", [])

        if not rows:
            st.info("아직 거래 내역이 없어요.")
            continue

        df = pd.DataFrame(rows, columns=headers)

        # 숫자 변환
        df["deposit"] = pd.to_numeric(df["deposit"], errors="coerce").fillna(0).astype(int)
        df["withdraw"] = pd.to_numeric(df["withdraw"], errors="coerce").fillna(0).astype(int)

        # 총액(누적)
        df["변동"] = df["deposit"] - df["withdraw"]
        df["총액"] = df["변동"].cumsum()

        # 날짜 포맷 변환(핵심)
        df["datetime"] = df["datetime"].apply(format_kr_datetime)

        view = df.rename(columns={
            "datetime": "날짜-시간",
            "memo": "내역",
            "deposit": "입금",
            "withdraw": "출금",
        })
        view = view[["날짜-시간", "내역", "입금", "출금", "총액"]]

        st.write(f"현재 총액: **{int(view['총액'].iloc[-1])} 포인트**")
        st.dataframe(view, use_container_width=True, hide_index=True)
