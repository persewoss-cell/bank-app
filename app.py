import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone, timedelta

# ✅ 너의 구글 Apps Script 웹앱 URL (/exec 로 끝나는 주소)
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzwbS_dIJGHTe4oyNK9QMWm0CXqqjgMJ3p-q0MQANqZ0mUQhrHPOIHVSgcH41vrLep-/exec"

st.set_page_config(page_title="학생 포인트 통장", layout="wide")
st.title("🏦 학생 포인트 통장")

# -------------------------
# 날짜시간 한국식 포맷
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
            if "T" in s and s.endswith("Z"):
                dt = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(KST)
            else:
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=KST)
                else:
                    dt = dt.astimezone(KST)
        except Exception:
            return s

    ampm = "오전" if dt.hour < 12 else "오후"
    hour12 = dt.hour % 12
    if hour12 == 0:
        hour12 = 12
    return f"{dt.year}년 {dt.month:02d}월 {dt.day:02d}일 {ampm} {hour12:02d}시 {dt.minute:02d}분"


# -------------------------
# Helpers
# -------------------------
def pin_ok(pin: str) -> bool:
    return pin.isdigit() and len(pin) == 4

def toast(msg: str, icon: str = "✅"):
    # streamlit 버전에 따라 toast가 없을 수 있어 fallback
    if hasattr(st, "toast"):
        st.toast(msg, icon=icon)
    else:
        st.success(msg)

# 세션 상태 초기화
if "saved_pins" not in st.session_state:
    st.session_state.saved_pins = {}   # {name: pin}
if "delete_confirm" not in st.session_state:
    st.session_state.delete_confirm = False
if "delete_target" not in st.session_state:
    st.session_state.delete_target = None
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False


# -------------------------
# API
# -------------------------
def api_get(params: dict):
    r = requests.get(WEBAPP_URL, params=params, timeout=15)
    return r.json()

def api_post(payload: dict):
    r = requests.post(WEBAPP_URL, json=payload, timeout=15)
    return r.json()

def api_list_accounts():
    return api_get({"action": "list_accounts"})

def api_create_account(name, pin):
    return api_post({"action":"create_account","name":name,"pin":pin})

def api_delete_account(name, pin):
    return api_post({"action":"delete_account","name":name,"pin":pin})

def api_add_tx(name, pin, memo, deposit, withdraw):
    return api_post({"action":"add_transaction","name":name,"pin":pin,"memo":memo,"deposit":int(deposit),"withdraw":int(withdraw)})

def api_undo_last(name, pin):
    return api_post({"action":"undo_last_transaction","name":name,"pin":pin})

def api_get_txs(name, pin):
    return api_get({"action":"get_transactions","name":name,"pin":pin})

def api_savings_list(name, pin):
    return api_get({"action":"list_savings","name":name,"pin":pin})

def api_savings_create(name, pin, principal, weeks):
    return api_post({"action":"savings_create","name":name,"pin":pin,"principal":int(principal),"weeks":int(weeks)})

def api_savings_close(name, pin, savings_id, mode):
    return api_post({"action":"savings_close","name":name,"pin":pin,"savings_id":savings_id,"mode":mode})

def api_admin_balances(admin_pin):
    return api_get({"action":"admin_balances","admin_pin":admin_pin})

def api_admin_reset_pin(admin_pin, name, new_pin):
    return api_post({"action":"admin_reset_pin","admin_pin":admin_pin,"name":name,"new_pin":new_pin})

def api_admin_backup(admin_pin):
    return api_post({"action":"admin_backup","admin_pin":admin_pin})


# -------------------------
# Sidebar: 계정 생성/삭제 + 관리자
# -------------------------
with st.sidebar:
    st.header("➕ 계정 만들기 / 삭제")

    new_name = st.text_input("이름(계정)", key="new_name").strip()
    new_pin  = st.text_input("비밀번호(4자리 숫자)", type="password", key="new_pin").strip()

    c1, c2 = st.columns(2)

    with c1:
        if st.button("계정 생성"):
            if not new_name:
                st.error("이름을 입력해 주세요.")
            elif not pin_ok(new_pin):
                st.error("비밀번호는 4자리 숫자여야 해요. (예: 0123)")
            else:
                res = api_create_account(new_name, new_pin)
                if res.get("ok"):
                    toast("계정 생성 완료!")
                    st.session_state.delete_confirm = False
                    # 입력칸 초기화는 pop 방식(충돌 방지)
                    st.session_state.pop("new_name", None)
                    st.session_state.pop("new_pin", None)
                    st.rerun()
                else:
                    st.error(res.get("error","계정 생성 실패"))

    with c2:
        if st.button("삭제"):
            # 확인 단계로 진입(팝업처럼)
            st.session_state.delete_confirm = True
            st.session_state.delete_target = (new_name, new_pin)

    # 삭제 확인 UI
    if st.session_state.delete_confirm:
        st.warning("정말로 삭제하시겠습니까?")
        st.caption("※ 삭제하면 해당 계정 탭(통장 내역)도 함께 삭제됩니다.")

        y, n = st.columns(2)
        with y:
            if st.button("예", key="delete_yes"):
                name, pin = st.session_state.delete_target or ("","")
                name = (name or "").strip()
                pin  = (pin or "").strip()

                if not name:
                    st.error("삭제할 이름(계정)을 입력해 주세요.")
                elif not pin_ok(pin):
                    st.error("비밀번호는 4자리 숫자여야 해요.")
                else:
                    res = api_delete_account(name, pin)
                    if res.get("ok"):
                        toast("삭제 완료!", icon="🗑️")
                        st.session_state.delete_confirm = False
                        st.session_state.delete_target = None
                        # 입력칸도 pop으로 정리(충돌 방지)
                        st.session_state.pop("new_name", None)
                        st.session_state.pop("new_pin", None)
                        # 저장된 PIN도 삭제
                        st.session_state.saved_pins.pop(name, None)
                        st.rerun()
                    else:
                        st.error(res.get("error","삭제 실패"))
        with n:
            if st.button("아니오", key="delete_no"):
                st.session_state.delete_confirm = False
                st.session_state.delete_target = None
                st.rerun()

    st.divider()

    # 관리자 모드
    with st.expander("🛡️ 관리자 모드", expanded=False):
        admin_pin = st.text_input("관리자 PIN", type="password", key="admin_pin").strip()

        if st.button("관리자 로그인"):
            # 서버에서 한번 확인(잔액조회 호출로 검증)
            res = api_admin_balances(admin_pin)
            if res.get("ok"):
                st.session_state.admin_ok = True
                toast("관리자 모드 ON", icon="🔓")
            else:
                st.session_state.admin_ok = False
                st.error(res.get("error","관리자 PIN 틀림"))

        if st.session_state.admin_ok:
            st.success("관리자 모드 활성화됨")

            # 백업
            if st.button("구글시트 백업 만들기"):
                res = api_admin_backup(admin_pin)
                if res.get("ok"):
                    toast(f"백업 생성: {res.get('backup_name')}", icon="💾")
                    st.info("Drive에 백업 파일이 생성되었습니다.")
                else:
                    st.error(res.get("error","백업 실패"))

            st.subheader("PIN 재설정")
            target = st.text_input("대상 학생 이름", key="reset_target").strip()
            newp   = st.text_input("새 PIN(4자리)", key="reset_pin", type="password").strip()
            if st.button("PIN 변경"):
                if not target:
                    st.error("대상 이름을 입력해 주세요.")
                elif not pin_ok(newp):
                    st.error("새 PIN은 4자리 숫자여야 해요.")
                else:
                    res = api_admin_reset_pin(admin_pin, target, newp)
                    if res.get("ok"):
                        toast("PIN 변경 완료!", icon="🔧")
                        st.session_state.saved_pins.pop(target, None)
                    else:
                        st.error(res.get("error","PIN 변경 실패"))

# -------------------------
# 계정 불러오기 + 검색
# -------------------------
accounts_res = api_list_accounts()
if not accounts_res.get("ok"):
    st.error(accounts_res.get("error","계정 목록을 불러오지 못했어요."))
    st.stop()

accounts = accounts_res.get("accounts", [])
if not accounts:
    st.info("아직 계정이 없어요. 왼쪽에서 계정을 먼저 만들어 주세요.")
    st.stop()

search = st.text_input("🔎 계정 검색(이름 일부)", key="search").strip()
filtered = [a for a in accounts if (search in a)] if search else accounts

if not filtered:
    st.warning("검색 결과가 없어요.")
    st.stop()

st.caption("상단 탭은 인터넷 탭처럼 계정을 전환합니다. (학생이 많으면 검색을 사용하세요.)")

# -------------------------
# 탭 UI
# -------------------------
tabs = st.tabs(filtered)

def calc_balance_from_df(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    return int((df["deposit"] - df["withdraw"]).cumsum().iloc[-1])

for idx, tab in enumerate(tabs):
    name = filtered[idx]
    with tab:
        st.markdown(f"## 🧾 {name} 통장")

        # PIN 입력 + 기억하기
        saved = st.session_state.saved_pins.get(name, "")
        pin_key = f"pin_{name}"

        if pin_key not in st.session_state and saved:
            st.session_state[pin_key] = saved

        pin = st.text_input(
            "비밀번호(4자리) 입력(조회/저장용)",
            type="password",
            key=pin_key
        ).strip()

        remember = st.checkbox("PIN 기억하기(이번 접속 동안)", value=bool(saved), key=f"remember_{name}")
        if remember and pin_ok(pin):
            st.session_state.saved_pins[name] = pin
        if not remember:
            st.session_state.saved_pins.pop(name, None)

        st.divider()

        # 통장 조회(먼저 불러와서 잔액 계산에 활용)
        df_view = None
        balance = None

        if pin_ok(pin):
            tx_res = api_get_txs(name, pin)
            if tx_res.get("ok"):
                headers = tx_res.get("headers", ["tx_id","datetime","memo","deposit","withdraw"])
                rows = tx_res.get("rows", [])
                if rows:
                    df = pd.DataFrame(rows, columns=headers)

                    # 숫자 변환
                    df["deposit"]  = pd.to_numeric(df["deposit"], errors="coerce").fillna(0).astype(int)
                    df["withdraw"] = pd.to_numeric(df["withdraw"], errors="coerce").fillna(0).astype(int)

                    df["변동"] = df["deposit"] - df["withdraw"]
                    df["총액"] = df["변동"].cumsum()

                    # 날짜 포맷 변환
                    df["datetime"] = df["datetime"].apply(format_kr_datetime)

                    df_view = df.rename(columns={
                        "datetime": "날짜-시간",
                        "memo": "내역",
                        "deposit": "입금",
                        "withdraw": "출금",
                    })[["날짜-시간","내역","입금","출금","총액"]]

                    balance = int(df["총액"].iloc[-1])
                else:
                    balance = 0
            else:
                st.error(tx_res.get("error","내역을 불러오지 못했어요."))

        # 상단 잔액 카드 느낌
        if balance is not None:
            st.write(f"### 현재 잔액: **{balance} 포인트**")
        else:
            st.info("통장 내역을 보려면 비밀번호(4자리 숫자)를 입력해 주세요.")

        st.divider()

        # -------------------------
        # 거래 기록
        # -------------------------
        st.subheader("📝 거래 기록(통장에 찍기)")

        # 입금/출금 자동 상호 초기화(콜백)
        dep_key = f"dep_{name}"
        wd_key  = f"wd_{name}"

        def on_dep_change():
            if st.session_state.get(dep_key, 0) > 0:
                st.session_state[wd_key] = 0

        def on_wd_change():
            if st.session_state.get(wd_key, 0) > 0:
                st.session_state[dep_key] = 0

        memo = st.text_input("내역", key=f"memo_{name}").strip()
        cA, cB = st.columns(2)
        with cA:
            deposit = st.number_input("입금", min_value=0, step=1, value=0, key=dep_key, on_change=on_dep_change)
        with cB:
            withdraw = st.number_input("출금", min_value=0, step=1, value=0, key=wd_key, on_change=on_wd_change)

        col_btn1, col_btn2 = st.columns([1,1])
        with col_btn1:
            if st.button("저장", key=f"save_{name}"):
                if not pin_ok(pin):
                    st.error("비밀번호(4자리 숫자)를 입력해 주세요.")
                elif not memo:
                    st.error("내역을 입력해 주세요.")
                elif (deposit > 0 and withdraw > 0) or (deposit == 0 and withdraw == 0):
                    st.error("입금/출금은 둘 중 하나만 입력해 주세요.")
                else:
                    res = api_add_tx(name, pin, memo, deposit, withdraw)
                    if res.get("ok"):
                        toast("저장 완료!", icon="✅")
                        # 입력칸 정리(충돌 없이 pop)
                        st.session_state.pop(f"memo_{name}", None)
                        st.session_state.pop(dep_key, None)
                        st.session_state.pop(wd_key, None)
                        st.rerun()
                    else:
                        st.error(res.get("error","저장 실패"))

        with col_btn2:
            if st.button("최근 1건 되돌리기", key=f"undo_{name}"):
                if not pin_ok(pin):
                    st.error("비밀번호(4자리 숫자)를 입력해 주세요.")
                else:
                    # 확인 단계(팝업처럼)
                    st.session_state[f"undo_confirm_{name}"] = True

        if st.session_state.get(f"undo_confirm_{name}", False):
            st.warning("정말로 최근 1건을 되돌리시겠습니까?")
            y, n = st.columns(2)
            with y:
                if st.button("예", key=f"undo_yes_{name}"):
                    res = api_undo_last(name, pin)
                    if res.get("ok"):
                        toast("최근 1건 되돌림 완료", icon="↩️")
                        st.session_state[f"undo_confirm_{name}"] = False
                        st.rerun()
                    else:
                        st.error(res.get("error","되돌리기 실패"))
            with n:
                if st.button("아니오", key=f"undo_no_{name}"):
                    st.session_state[f"undo_confirm_{name}"] = False
                    st.rerun()

        st.divider()

        # -------------------------
        # 적금
        # -------------------------
        st.subheader("🏦 적금")

        if not pin_ok(pin):
            st.info("적금을 사용하려면 비밀번호(4자리 숫자)를 입력해 주세요.")
        else:
            # 적금 가입
            c1, c2, c3 = st.columns([2,2,2])
            with c1:
                principal = st.number_input("적금 원금", min_value=0, step=1, value=0, key=f"sv_principal_{name}")
            with c2:
                weeks = st.selectbox("기간(주)", options=list(range(1,11)), index=4, key=f"sv_weeks_{name}")
            with c3:
                rate = weeks * 5
                st.metric("이자율", f"{rate}%")

            if st.button("적금 가입", key=f"sv_join_{name}"):
                if principal <= 0:
                    st.error("원금을 1 이상으로 입력해 주세요.")
                elif balance is not None and principal > balance:
                    st.error("원금이 현재 잔액보다 커요.")
                else:
                    res = api_savings_create(name, pin, principal, weeks)
                    if res.get("ok"):
                        toast("적금 가입 완료!", icon="🏦")
                        st.rerun()
                    else:
                        st.error(res.get("error","적금 가입 실패"))

            # 적금 목록/현황
            sav_res = api_savings_list(name, pin)
            if not sav_res.get("ok"):
                st.error(sav_res.get("error","적금 목록을 불러오지 못했어요."))
            else:
                savings = sav_res.get("savings", [])
                active = [s for s in savings if s["status"] == "active"]
                if not savings:
                    st.info("적금 내역이 없어요.")
                else:
                    # 요약(진행 중)
                    active_principal = sum(s["principal"] for s in active)
                    active_interest  = sum(s["interest"] for s in active)
                    st.write(f"진행 중 적금 원금 합계: **{active_principal}** / 만기 시 이자 합계: **{active_interest}**")

                    # 테이블
                    table = []
                    for s in savings:
                        table.append({
                            "상태": s["status"],
                            "원금": s["principal"],
                            "기간(주)": s["weeks"],
                            "이자": s["interest"],
                            "만기일": format_kr_datetime(s["maturity_datetime"]),
                            "ID": s["savings_id"],
                        })
                    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

                    # 적금 처리(만기/해지)
                    st.caption("만기 처리(만기 후) 또는 해지(만기 전 가능)")
                    for s in active:
                        sid = s["savings_id"]
                        cols = st.columns([3,1,1])
                        cols[0].write(f"• 원금 {s['principal']} / {s['weeks']}주 / 만기 {format_kr_datetime(s['maturity_datetime'])} (이자 {s['interest']})")

                        if cols[1].button("만기 받기", key=f"mature_{name}_{sid}"):
                            res = api_savings_close(name, pin, sid, "mature")
                            if res.get("ok"):
                                toast(f"만기 지급 완료: {res.get('paid')} 포인트", icon="🎁")
                                st.rerun()
                            else:
                                st.error(res.get("error","만기 처리 실패"))

                        if cols[2].button("해지", key=f"cancel_{name}_{sid}"):
                            st.session_state[f"cancel_confirm_{name}_{sid}"] = True

                        if st.session_state.get(f"cancel_confirm_{name}_{sid}", False):
                            st.warning("정말로 해지하시겠습니까? (만기 전 해지는 원금만 반환)")
                            y, n = st.columns(2)
                            with y:
                                if st.button("예", key=f"cancel_yes_{name}_{sid}"):
                                    res = api_savings_close(name, pin, sid, "cancel")
                                    if res.get("ok"):
                                        toast(f"해지 완료: {res.get('refunded')} 포인트 반환", icon="🧾")
                                        st.session_state[f"cancel_confirm_{name}_{sid}"] = False
                                        st.rerun()
                                    else:
                                        st.error(res.get("error","해지 실패"))
                            with n:
                                if st.button("아니오", key=f"cancel_no_{name}_{sid}"):
                                    st.session_state[f"cancel_confirm_{name}_{sid}"] = False
                                    st.rerun()

        st.divider()

        # -------------------------
        # 통장 내역 표
        # -------------------------
        st.subheader("📒 통장 내역")
        if df_view is None:
            st.info("아직 거래 내역이 없거나, 비밀번호가 필요해요.")
        else:
            st.dataframe(df_view, use_container_width=True, hide_index=True)

        # -------------------------
        # 관리자용: 전체 잔액(탭 내부에서도 확인 가능)
        # -------------------------
        if st.session_state.admin_ok:
            st.divider()
            st.subheader("🛡️ 관리자: 전체 잔액 현황")
            admin_pin = st.session_state.get("admin_pin","").strip()
            res = api_admin_balances(admin_pin)
            if res.get("ok"):
                bdf = pd.DataFrame(res["balances"])
                st.dataframe(bdf, use_container_width=True, hide_index=True)
            else:
                st.error(res.get("error","관리자 잔액 조회 실패"))
