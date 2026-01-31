import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timezone, timedelta, date

# =========================
# 설정
# =========================
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzwbS_dIJGHTe4oyNK9QMWm0CXqqjgMJ3p-q0MQANqZ0mUQhrHPOIHVSgcH41vrLep-/exec"

st.set_page_config(page_title="학생 포인트 통장", layout="wide")
st.title("🏦 학생 포인트 통장")

KST = timezone(timedelta(hours=9))
SESSION = requests.Session()

# =========================
# 공통 유틸
# =========================
def pin_ok(pin: str) -> bool:
    return pin.isdigit() and len(pin) == 4

def toast(msg: str, icon: str = "✅"):
    if hasattr(st, "toast"):
        st.toast(msg, icon=icon)
    else:
        st.success(msg)

def format_kr_datetime(val) -> str:
    if val is None or val == "":
        return ""
    if isinstance(val, datetime):
        dt = val.astimezone(KST) if val.tzinfo else val.replace(tzinfo=KST)
    else:
        s = str(val).strip()
        try:
            if "T" in s and s.endswith("Z"):
                dt = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(KST)
            else:
                dt = datetime.fromisoformat(s)
                dt = dt.astimezone(KST) if dt.tzinfo else dt.replace(tzinfo=KST)
        except Exception:
            return s

    ampm = "오전" if dt.hour < 12 else "오후"
    hour12 = dt.hour % 12
    hour12 = 12 if hour12 == 0 else hour12
    return f"{dt.year}년 {dt.month:02d}월 {dt.day:02d}일 {ampm} {hour12:02d}시 {dt.minute:02d}분"

def rate_by_weeks(weeks: int) -> float:
    return weeks * 0.05  # 1주=5%

def compute_preview(principal: int, weeks: int):
    r = rate_by_weeks(weeks)
    interest = round(principal * r)
    maturity = principal + interest
    maturity_date = (datetime.now(KST) + timedelta(days=weeks * 7)).date()
    return r, interest, maturity, maturity_date

def parse_iso_to_date(iso_str: str):
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return dt.date()
    except Exception:
        return None

def build_df(headers, rows):
    if not rows:
        return pd.DataFrame(columns=["tx_id", "datetime", "memo", "deposit", "withdraw", "총액"])
    df = pd.DataFrame(rows, columns=headers)
    df["deposit"] = pd.to_numeric(df["deposit"], errors="coerce").fillna(0).astype(int)
    df["withdraw"] = pd.to_numeric(df["withdraw"], errors="coerce").fillna(0).astype(int)
    df["변동"] = df["deposit"] - df["withdraw"]
    df["총액"] = df["변동"].cumsum()
    df["datetime"] = df["datetime"].apply(format_kr_datetime)
    return df

# =========================
# API 로그(사이드바에 누적 표시)
# =========================
def log_api(res: dict, label: str = ""):
    if "api_logs" not in st.session_state:
        st.session_state.api_logs = []

    st.session_state.api_logs.append({
        "t": datetime.now(KST).strftime("%H:%M:%S"),
        "label": label or res.get("_action", ""),
        "action": res.get("_action", ""),
        "time": res.get("_client_seconds", None),
        "status": res.get("_status", None),
        "ok": res.get("ok", None),
        "error": res.get("error", ""),
    })
    st.session_state.api_logs = st.session_state.api_logs[-30:]

def show_api_logs():
    with st.sidebar:
        st.markdown("### ⏱ 최근 API")
        logs = st.session_state.get("api_logs", [])
        if not logs:
            st.caption("아직 호출 기록이 없어요.")
            return
        for x in reversed(logs[-10:]):
            st.write(f"- {x['t']}  | label: {x['label']}\n  action: {x['action']}\n  time: {x['time']}s\n  status: {x['status']} / ok:{x['ok']}")
            if x["error"]:
                st.caption("  ↳ " + x["error"])

# =========================
# API wrappers (시간 측정 포함)
# =========================
def api_get(params: dict):
    t0 = time.perf_counter()
    r = SESSION.get(WEBAPP_URL, params=params, timeout=60)
    dt = time.perf_counter() - t0

    try:
        j = r.json()
    except Exception:
        j = {"ok": False, "error": "JSON parse 실패", "raw": r.text[:300]}

    j["_client_seconds"] = round(dt, 3)
    j["_status"] = r.status_code
    j["_action"] = params.get("action", "")
    log_api(j, label=j.get("_action", "api_get"))
    return j

def api_post(payload: dict):
    t0 = time.perf_counter()
    r = SESSION.post(WEBAPP_URL, json=payload, timeout=60)
    dt = time.perf_counter() - t0

    try:
        j = r.json()
    except Exception:
        j = {"ok": False, "error": "JSON parse 실패", "raw": r.text[:300]}

    j["_client_seconds"] = round(dt, 3)
    j["_status"] = r.status_code
    j["_action"] = payload.get("action", "")
    log_api(j, label=j.get("_action", "api_post"))
    return j
    
def api_get_snapshot(name, pin):
    return api_get({"action": "get_snapshot", "name": name, "pin": pin})

# =========================
# 캐시(자주 안 바뀌는 것)
# =========================
@st.cache_data(ttl=30, show_spinner=False)
def api_list_accounts_cached():
    return api_get({"action": "list_accounts"})

@st.cache_data(ttl=300, show_spinner=False)
def api_list_templates_cached():
    return api_get({"action": "list_templates"})

@st.cache_data(ttl=120, show_spinner=False)
def api_get_goal_cached(name, pin):
    return api_get({"action": "get_goal", "name": name, "pin": pin})

# =========================
# API 간단 함수들
# =========================
def api_create_account(name, pin):
    return api_post({"action": "create_account", "name": name, "pin": pin})

def api_delete_account(name, pin):
    return api_post({"action": "delete_account", "name": name, "pin": pin})

def api_add_tx(name, pin, memo, deposit, withdraw):
    return api_post({"action": "add_transaction", "name": name, "pin": pin,
                     "memo": memo, "deposit": int(deposit), "withdraw": int(withdraw)})

def api_get_txs(name, pin):
    return api_get({"action": "get_transactions", "name": name, "pin": pin})

def api_undo_last_n(name, pin, n):
    return api_post({"action": "undo_last_n", "name": name, "pin": pin, "n": int(n)})

def api_savings_list(name, pin):
    return api_get({"action": "list_savings", "name": name, "pin": pin})

def api_savings_create(name, pin, principal, weeks):
    return api_post({"action": "savings_create", "name": name, "pin": pin,
                     "principal": int(principal), "weeks": int(weeks)})

def api_savings_cancel(name, pin, savings_id):
    return api_post({"action": "savings_cancel", "name": name, "pin": pin, "savings_id": savings_id})

def api_process_maturities(name, pin):
    return api_get({"action": "process_maturities", "name": name, "pin": pin})

def api_set_goal(name, pin, goal_amount, goal_date_str):
    return api_post({"action": "set_goal", "name": name, "pin": pin,
                     "goal_amount": int(goal_amount), "goal_date": goal_date_str})

# =========================
# Session state
# =========================
if "saved_pins" not in st.session_state:
    st.session_state.saved_pins = {}
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False
if "data" not in st.session_state:
    st.session_state.data = {}  # {name: {df,balance,savings,ts}}
if "last_maturity_check" not in st.session_state:
    st.session_state.last_maturity_check = {}  # {name: datetime}
if "tpl_prev" not in st.session_state:
    st.session_state.tpl_prev = {}  # {name: prev_label}

# =========================
# 데이터 로딩(한 계정 기준)
# =========================
def refresh_account_data(name: str, pin: str, force: bool = False):
    """한 계정의 화면 데이터를 session_state에 저장.
    snapshot 한 번만 호출해서 tx/savings/goal/balance/maturity까지 모두 받음.
    """
    now = datetime.now(KST)
    slot = st.session_state.data.get(name, {})
    last_ts = slot.get("ts")

    # 너무 자주 호출 방지(3초 내 재호출이면 스킵)
    if (not force) and last_ts and (now - last_ts).total_seconds() < 3:
        return

    snap = api_get_snapshot(name, pin)
    if not snap.get("ok"):
        st.session_state.data[name] = {"error": snap.get("error", "스냅샷 로드 실패"), "ts": now}
        return

    df = build_df(
        snap.get("headers", ["tx_id", "datetime", "memo", "deposit", "withdraw"]),
        snap.get("rows", [])
    )

    st.session_state.data[name] = {
        "df": df,
        "balance": int(snap.get("balance", 0) or 0),
        "savings": snap.get("savings", []),
        "goal": {
            "ok": True,
            "goal_amount": int(snap.get("goal_amount", 0) or 0),
            "goal_date": str(snap.get("goal_date", "") or "")
        },
        "matured_count": int(snap.get("matured_count", 0) or 0),
        "paid_total": int(snap.get("paid_total", 0) or 0),
        "ts": now
    }

# =========================
# Sidebar - 계정 생성/삭제
# =========================
with st.sidebar:
    st.header("➕ 계정 만들기 / 삭제")

    new_name = st.text_input("이름(계정)", key="new_name").strip()
    new_pin = st.text_input("비밀번호(4자리 숫자)", type="password", key="new_pin").strip()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("계정 생성"):
            if not new_name:
                st.error("이름을 입력해 주세요.")
            elif not pin_ok(new_pin):
                st.error("비밀번호는 4자리 숫자여야 해요.")
            else:
                res = api_create_account(new_name, new_pin)
                if res.get("ok"):
                    toast("계정 생성 완료!")
                    st.session_state.pop("new_name", None)
                    st.session_state.pop("new_pin", None)
                    api_list_accounts_cached.clear()
                    st.rerun()
                else:
                    st.error(res.get("error", "계정 생성 실패"))

    with c2:
        if st.button("계정 삭제"):
            st.session_state["delete_confirm"] = True

    if st.session_state.get("delete_confirm", False):
        st.warning("정말로 삭제하시겠습니까?")
        st.caption("※ 삭제하면 거래/적금/목표 기록도 함께 삭제됩니다.")
        y, n = st.columns(2)
        with y:
            if st.button("예"):
                if not new_name:
                    st.error("삭제할 이름(계정)을 입력해 주세요.")
                elif not pin_ok(new_pin):
                    st.error("비밀번호는 4자리 숫자여야 해요.")
                else:
                    res = api_delete_account(new_name, new_pin)
                    if res.get("ok"):
                        toast("삭제 완료!", icon="🗑️")
                        st.session_state["delete_confirm"] = False
                        st.session_state.saved_pins.pop(new_name, None)
                        st.session_state.data.pop(new_name, None)
                        api_list_accounts_cached.clear()
                        st.rerun()
                    else:
                        st.error(res.get("error", "삭제 실패"))
        with n:
            if st.button("아니오"):
                st.session_state["delete_confirm"] = False
                st.rerun()

# =========================
# 메인: 계정 선택(한 계정만 로딩)
# =========================
accounts_res = api_list_accounts_cached()
if not accounts_res.get("ok"):
    st.error(accounts_res.get("error", "계정 목록을 불러오지 못했어요."))
    show_api_logs()
    st.stop()

accounts = accounts_res.get("accounts", [])
if not accounts:
    st.info("아직 계정이 없어요. 왼쪽에서 계정을 먼저 만들어 주세요.")
    show_api_logs()
    st.stop()

tpl_res = api_list_templates_cached()
TEMPLATES = tpl_res.get("templates", []) if tpl_res.get("ok") else []
TEMPLATE_BY_LABEL = {t["label"]: t for t in TEMPLATES}

search = st.text_input("🔎 계정 검색(이름 일부)", key="search").strip()
filtered = [a for a in accounts if (search in a)] if search else accounts
if not filtered:
    st.warning("검색 결과가 없어요.")
    show_api_logs()
    st.stop()

st.caption("계정을 선택하세요 (한 계정만 불러와서 속도가 빨라집니다)")
if hasattr(st, "segmented_control"):
    name = st.segmented_control("계정", options=filtered, default=filtered[0], key="selected_account")
else:
    name = st.radio("계정", filtered, horizontal=True, key="selected_account")

st.markdown(f"## 🧾 {name} 통장")

# PIN
saved = st.session_state.saved_pins.get(name, "")
pin_key = f"pin_{name}"
if pin_key not in st.session_state and saved:
    st.session_state[pin_key] = saved

pin = st.text_input("비밀번호(4자리) 입력(조회/저장용)", type="password", key=pin_key).strip()
remember = st.checkbox("PIN 기억하기(이번 접속 동안)", value=bool(saved), key=f"remember_{name}")

if remember and pin_ok(pin):
    st.session_state.saved_pins[name] = pin
if not remember:
    st.session_state.saved_pins.pop(name, None)

if not pin_ok(pin):
    st.info("비밀번호(4자리 숫자)를 입력하면 통장 기능이 활성화돼요.")
    show_api_logs()
    st.stop()

# 만기 자동 처리(2분에 1번만)
refresh_account_data(name, pin, force=False)
slot = st.session_state.data.get(name, {})
if slot.get("error"):
    st.error(slot["error"])
    st.stop()

# ✅ snapshot 안에 만기 처리 결과가 들어있음
if slot.get("matured_count", 0) > 0:
    st.success(f"🎉 만기 도착! 적금 {slot['matured_count']}건 자동 반환 (+{slot['paid_total']} 포인트)")

# =========================
# 화면 탭
# =========================
sub1, sub2, sub3 = st.tabs(["📝 거래", "💰 적금", "🎯 목표"])

# -------------------------
# 1) 거래
# -------------------------
with sub1:
    st.subheader("📝 거래 기록(통장에 찍기)")

    memo_key = f"memo_{name}"
    dep_key = f"dep_{name}"
    wd_key = f"wd_{name}"
    tpl_sel_key = f"tpl_sel_{name}"
    clear_flag = f"tx_clear_{name}"

    # 초기화 플래그(다음 run에서 위젯 생성 전에 초기화)
    if clear_flag not in st.session_state:
        st.session_state[clear_flag] = False
    if memo_key not in st.session_state:
        st.session_state[memo_key] = ""
    if dep_key not in st.session_state:
        st.session_state[dep_key] = 0
    if wd_key not in st.session_state:
        st.session_state[wd_key] = 0
    if tpl_sel_key not in st.session_state:
        st.session_state[tpl_sel_key] = "(직접 입력)"

    if st.session_state[clear_flag]:
        st.session_state[memo_key] = ""
        st.session_state[dep_key] = 0
        st.session_state[wd_key] = 0
        st.session_state[tpl_sel_key] = "(직접 입력)"
        st.session_state[clear_flag] = False

    labels = ["(직접 입력)"] + [t["label"] for t in TEMPLATES]
    sel = st.selectbox("내역 템플릿", labels, key=tpl_sel_key)

    # ✅ on_change 없이 “선택 바뀐 것 감지”로 자동입력 (콜백 문제 0)
    prev = st.session_state.tpl_prev.get(name)
    if sel != prev:
        st.session_state.tpl_prev[name] = sel
        if sel != "(직접 입력)":
            tpl = TEMPLATE_BY_LABEL.get(sel)
            if tpl:
                st.session_state[memo_key] = tpl["label"]
                amt = int(tpl["amount"])
                if tpl["kind"] == "deposit":
                    st.session_state[dep_key] = amt
                    st.session_state[wd_key] = 0
                else:
                    st.session_state[wd_key] = amt
                    st.session_state[dep_key] = 0

    st.text_input("내역", key=memo_key)

    st.caption("빠른 입금")
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("+10", key=f"q10_{name}"):
            st.session_state[dep_key] = int(st.session_state[dep_key]) + 10
            st.session_state[wd_key] = 0
            st.rerun()
    with b2:
        if st.button("+50", key=f"q50_{name}"):
            st.session_state[dep_key] = int(st.session_state[dep_key]) + 50
            st.session_state[wd_key] = 0
            st.rerun()
    with b3:
        if st.button("+100", key=f"q100_{name}"):
            st.session_state[dep_key] = int(st.session_state[dep_key]) + 100
            st.session_state[wd_key] = 0
            st.rerun()

    cA, cB = st.columns(2)
    with cA:
        st.number_input("입금", min_value=0, step=1, key=dep_key)
    with cB:
        st.number_input("출금", min_value=0, step=1, key=wd_key)

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("저장", key=f"save_{name}"):
            memo = st.session_state[memo_key].strip()
            deposit = int(st.session_state[dep_key])
            withdraw = int(st.session_state[wd_key])

            if not memo:
                st.error("내역을 입력해 주세요.")
            elif (deposit > 0 and withdraw > 0) or (deposit == 0 and withdraw == 0):
                st.error("입금/출금은 둘 중 하나만 입력해 주세요.")
            elif withdraw > balance:
                st.error("출금 금액이 현재 잔액보다 커요.")
            else:
                res = api_add_tx(name, pin, memo, deposit, withdraw)
                if res.get("ok"):
                    toast("저장 완료!", icon="✅")
                    st.session_state[clear_flag] = True
                    refresh_account_data(name, pin, force=True)
                    st.rerun()
                else:
                    st.error(res.get("error", "저장 실패"))

    with col_btn2:
        undo_n = st.selectbox("되돌리기(최근)", [1, 2, 3], index=0, key=f"undo_n_{name}")
        if st.button("되돌리기", key=f"undo_btn_{name}"):
            st.session_state[f"undo_confirm_{name}"] = True

    if st.session_state.get(f"undo_confirm_{name}", False):
        st.warning(f"정말로 최근 {undo_n}건을 되돌리시겠습니까?")
        y, n = st.columns(2)
        with y:
            if st.button("예", key=f"undo_yes_{name}"):
                res = api_undo_last_n(name, pin, undo_n)
                if res.get("ok"):
                    toast(f"최근 {undo_n}건 되돌림 완료", icon="↩️")
                    st.session_state[f"undo_confirm_{name}"] = False
                    refresh_account_data(name, pin, force=True)
                    st.rerun()
                else:
                    st.error(res.get("error", "되돌리기 실패"))
        with n:
            if st.button("아니오", key=f"undo_no_{name}"):
                st.session_state[f"undo_confirm_{name}"] = False
                st.rerun()

# -------------------------
# 2) 적금
# -------------------------
with sub2:
    st.subheader("💰 적금")

    p = st.number_input("적금 원금(10단위)", min_value=10, step=10, value=100, key=f"sv_p_{name}")
    w = st.selectbox("기간(1~10주)", list(range(1, 11)), index=4, key=f"sv_w_{name}")

    r, interest, maturity_amt, maturity_date = compute_preview(int(p), int(w))
    st.info(
        f"✅ 미리보기\n\n"
        f"- 이자율: **{int(r*100)}%**\n"
        f"- 만기일: **{maturity_date.strftime('%Y-%m-%d')}**\n"
        f"- 만기 수령액: **{maturity_amt} 포인트** (원금 {p} + 이자 {interest})"
    )

    if p > balance:
        st.warning("⚠️ 현재 잔액보다 원금이 커서 가입할 수 없어요.")

    if st.button("적금 가입", key=f"sv_join_{name}", disabled=(p > balance)):
        res = api_savings_create(name, pin, int(p), int(w))
        if res.get("ok"):
            toast("적금 가입 완료!", icon="💰")
            refresh_account_data(name, pin, force=True)
            st.rerun()
        else:
            st.error(res.get("error", "적금 가입 실패"))

    st.divider()

    # 캐시된 savings 사용
    savings = st.session_state.data.get(name, {}).get("savings", [])
    if not savings:
        st.info("적금이 아직 없어요.")
    else:
        active = [s for s in savings if s.get("status") == "active"]
        matured = [s for s in savings if s.get("status") == "matured"]
        canceled = [s for s in savings if s.get("status") == "canceled"]

        if active:
            st.markdown("### 🟢 진행 중 적금")
            for s in active:
                sid = s["savings_id"]
                principal = int(s["principal"])
                weeks = int(s["weeks"])
                interest2 = int(s["interest"])
                maturity_dt = format_kr_datetime(s["maturity_datetime"])
                st.write(f"- 원금 **{principal}**, 기간 **{weeks}주**, 만기일 **{maturity_dt}**, 만기 이자 **{interest2}**")

                if st.button("해지", key=f"sv_cancel_btn_{name}_{sid}"):
                    st.session_state[f"sv_cancel_confirm_{sid}"] = True

                if st.session_state.get(f"sv_cancel_confirm_{sid}", False):
                    st.warning("정말로 해지하시겠습니까? (원금만 반환)")
                    y, n = st.columns(2)
                    with y:
                        if st.button("예", key=f"sv_cancel_yes_{name}_{sid}"):
                            res = api_savings_cancel(name, pin, sid)
                            if res.get("ok"):
                                toast(f"해지 완료! (+{res.get('refunded',0)})", icon="🧾")
                                st.session_state[f"sv_cancel_confirm_{sid}"] = False
                                refresh_account_data(name, pin, force=True)
                                st.rerun()
                            else:
                                st.error(res.get("error", "해지 실패"))
                    with n:
                        if st.button("아니오", key=f"sv_cancel_no_{name}_{sid}"):
                            st.session_state[f"sv_cancel_confirm_{sid}"] = False
                            st.rerun()

        if matured:
            st.markdown("### 🔵 만기(자동 반환 완료)")
            for s in matured[:10]:
                st.write(f"- 원금 {int(s['principal'])}, {int(s['weeks'])}주, 이자 {int(s['interest'])}")

        if canceled:
            st.markdown("### ⚪ 해지 기록")
            for s in canceled[:10]:
                st.write(f"- 원금 {int(s['principal'])}, {int(s['weeks'])}주")

# -------------------------
# 3) 목표 (goal은 여기서만 호출 + 캐시)
# -------------------------
with sub3:
    st.subheader("🎯 목표 저금(목표 설정/달성률)")

    goal = api_get_goal_cached(name, pin)
    if not goal.get("ok"):
        st.error(goal.get("error", "목표 정보를 불러오지 못했어요."))
    else:
        cur_goal_amt = int(goal.get("goal_amount", 0) or 0)
        cur_goal_date = str(goal.get("goal_date", "") or "")

        c1, c2 = st.columns(2)
        with c1:
            g_amt = st.number_input(
                "목표 금액",
                min_value=1,
                step=1,
                value=cur_goal_amt if cur_goal_amt > 0 else 100,
                key=f"goal_amt_{name}",
            )
        with c2:
            default_date = date.today() + timedelta(days=30)
            if cur_goal_date:
                try:
                    default_date = datetime.fromisoformat(cur_goal_date).date()
                except Exception:
                    pass
            g_date = st.date_input("목표 날짜", value=default_date, key=f"goal_date_{name}")

        if st.button("목표 저장", key=f"goal_save_{name}"):
            res = api_set_goal(name, pin, int(g_amt), g_date.isoformat())
            if res.get("ok"):
                toast("목표 저장 완료!", icon="🎯")
                api_get_goal_cached.clear()
                st.rerun()
            else:
                st.error(res.get("error", "목표 저장 실패"))

        goal_amount = int(g_amt)
        goal_date = g_date
        current_balance = int(balance)

        savings_list = st.session_state.data.get(name, {}).get("savings", [])
        bonus = 0
        for s in savings_list:
            if str(s.get("status", "")).lower() != "active":
                continue
            m_date = parse_iso_to_date(s.get("maturity_datetime", ""))
            if not m_date:
                continue
            if m_date <= goal_date:
                principal = int(float(s.get("principal", 0) or 0))
                interest3 = int(float(s.get("interest", 0) or 0))
                bonus += (principal + interest3)

        expected_amount = current_balance + bonus
        now_ratio = min(1.0, current_balance / goal_amount) if goal_amount > 0 else 0.0
        exp_ratio = min(1.0, expected_amount / goal_amount) if goal_amount > 0 else 0.0

        st.write(f"현재 잔액 기준: **{now_ratio*100:.1f}%**  (현재 {current_balance} / 목표 {goal_amount})")
        st.progress(exp_ratio)
        st.write(f"목표일까지 예상 달성률: **{exp_ratio*100:.1f}%**  (예상 {expected_amount} / 목표 {goal_amount})")

        if bonus > 0:
            st.info(f"📌 목표 날짜({goal_date.isoformat()}) 이전 만기 적금 수령액(원금+이자) **+{bonus}** 포함")
        else:
            st.caption(f"목표 날짜({goal_date.isoformat()}) 이전 만기 적금이 없어 예상 금액은 현재 잔액과 같아요.")

# =========================
# 통장 내역
# =========================
st.subheader("📒 통장 내역")
if len(df) == 0:
    st.info("아직 거래 내역이 없어요.")
else:
    view = df.rename(columns={"datetime": "날짜-시간", "memo": "내역", "deposit": "입금", "withdraw": "출금"})[
        ["날짜-시간", "내역", "입금", "출금", "총액"]
    ]
    st.dataframe(view, use_container_width=True, hide_index=True)

# ✅ 사이드바에 최근 API 로그 표시
show_api_logs()
