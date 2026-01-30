import streamlit as st
import pandas as pd
import requests

WEBAPP_URL = "여기에_너의_웹앱_URL"  # https://script.google.com/macros/s/.../exec

st.set_page_config(page_title="학생 포인트 통장", layout="wide")
st.title("🏦 학생 포인트 통장")

# -------------------------
# API helpers
# -------------------------
def api_list_accounts():
    r = requests.get(WEBAPP_URL, params={"action": "list_accounts"}, timeout=10)
    return r.json()

def api_create_account(name, pin):
    r = requests.post(WEBAPP_URL, json={"action": "create_account", "name": name, "pin": pin}, timeout=10)
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
# Sidebar: account creation
# -------------------------
with st.sidebar:
    st.header("➕ 계정 만들기")
    new_name = st.text_input("이름(계정)", key="new_name").strip()
    new_pin = st.text_input("비밀번호(4자리 숫자)", type="password", key="new_pin").strip()

    if st.button("계정 생성"):
        if not new_name:
            st.error("이름을 입력해 주세요.")
        elif not pin_ok(new_pin):
            st.error("비밀번호는 4자리 숫자여야 해요. (예: 0123)")
        else:
            res = api_create_account(new_name, new_pin)
            if res.get("ok"):
                st.success("계정 생성 완료! 왼쪽에서 계정을 선택하세요.")
                st.rerun()
            else:
                st.error(res.get("error", "계정 생성 실패"))


# -------------------------
# Main: select account
# -------------------------
accounts_res = api_list_accounts()
accounts = accounts_res.get("accounts", []) if accounts_res.get("ok") else []

st.subheader("👤 계정 선택")
if not accounts:
    st.info("아직 계정이 없어요. 왼쪽(사이드바)에서 계정을 먼저 만들어 주세요.")
    st.stop()

selected = st.selectbox("계정(이름)", options=accounts, key="selected_account")
pin = st.text_input("비밀번호(4자리) 입력(조회/저장용)", type="password", key="pin_main").strip()

st.divider()

# -------------------------
# Add transaction (requires PIN)
# -------------------------
st.subheader("📝 거래 기록(통장에 찍기)")
memo = st.text_input("내역", key="memo").strip()
c1, c2 = st.columns(2)
with c1:
    deposit = st.number_input("입금", min_value=0, step=1, value=0)
with c2:
    withdraw = st.number_input("출금", min_value=0, step=1, value=0)

if st.button("통장에 기록하기(저장)"):
    if not pin_ok(pin):
        st.error("비밀번호(4자리 숫자)를 입력해 주세요.")
    elif not memo:
        st.error("내역을 입력해 주세요.")
    elif (deposit > 0 and withdraw > 0) or (deposit == 0 and withdraw == 0):
        st.error("입금/출금은 둘 중 하나만 입력해 주세요.")
    else:
        res = api_add_tx(selected, pin, memo, deposit, withdraw)
        if res.get("ok"):
            st.success("저장 완료!")
            st.rerun()
        else:
            st.error(res.get("error", "저장 실패"))

st.divider()

# -------------------------
# Show passbook (requires PIN)
# -------------------------
st.subheader("📒 통장 내역")
if not pin_ok(pin):
    st.info("통장 내역을 보려면 비밀번호(4자리 숫자)를 입력해 주세요.")
    st.stop()

tx_res = api_get_txs(selected, pin)
if not tx_res.get("ok"):
    st.error(tx_res.get("error", "내역을 불러오지 못했어요."))
    st.stop()

headers = tx_res.get("headers", ["datetime", "memo", "deposit", "withdraw"])
rows = tx_res.get("rows", [])

if not rows:
    st.info("아직 거래 내역이 없어요.")
    st.stop()

df = pd.DataFrame(rows, columns=headers)

# 숫자 변환
df["deposit"] = pd.to_numeric(df["deposit"], errors="coerce").fillna(0).astype(int)
df["withdraw"] = pd.to_numeric(df["withdraw"], errors="coerce").fillna(0).astype(int)

df["변동"] = df["deposit"] - df["withdraw"]
df["총액"] = df["변동"].cumsum()

view = df.rename(columns={
    "datetime": "날짜-시간",
    "memo": "내역",
    "deposit": "입금",
    "withdraw": "출금",
})
view = view[["날짜-시간", "내역", "입금", "출금", "총액"]]

st.write(f"현재 총액: **{int(view['총액'].iloc[-1])} 포인트**")
st.dataframe(view, use_container_width=True, hide_index=True)
