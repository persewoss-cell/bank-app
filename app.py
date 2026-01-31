import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone, timedelta, date

WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzwbS_dIJGHTe4oyNK9QMWm0CXqqjgMJ3p-q0MQANqZ0mUQhrHPOIHVSgcH41vrLep-/exec"

st.set_page_config(page_title="학생 포인트 통장", layout="wide")
st.title("🏦 학생 포인트 통장")

KST = timezone(timedelta(hours=9))


# -------------------------
# Utils
# -------------------------
def format_kr_datetime(val) -> str:
    if val is None or val == "":
        return ""
    # GAS에서 Date가 올 때 ISO(…Z) 형태가 많음
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


def pin_ok(pin: str) -> bool:
    return pin.isdigit() and len(pin) == 4


def toast(msg: str, icon: str = "✅"):
    if hasattr(st, "toast"):
        st.toast(msg, icon=icon)
    else:
        st.success(msg)


def rate_by_weeks(weeks: int) -> float:
    # 1주=5%, 10주=50% (주*5%)
    return weeks * 0.05


def compute_preview(principal: int, weeks: int):
    r = rate_by_weeks(weeks)
    interest = round(principal * r)  # 원 단위 반올림
    maturity = principal + interest
    maturity_date = (datetime.now(KST) + timedelta(days=weeks * 7)).date()
    return r, interest, maturity, maturity_date


# -------------------------
# API wrappers
# -------------------------
def api_get(params: dict):
    r = requests.get(WEBAPP_URL, params=params, timeout=20)
    return r.json()


def api_post(payload: dict):
    r = requests.post(WEBAPP_URL, json=payload, timeout=20)
    return r.json()


def api_list_accounts():
    return api_get({"action": "list_accounts"})


def api_list_templates():
    return api_get({"action": "list_templates"})


def api_create_account(name, pin):
    return api_post({"action": "create_account", "name": name, "pin": pin})


def api_delete_account(name, pin):
    return api_post({"action": "delete_account", "name": name, "pin": pin})


def api_add_tx(name, pin, memo, deposit, withdraw):
    return api_post(
        {"action": "add_transaction", "name": name, "pin": pin, "memo": memo,
         "deposit": int(deposit), "withdraw": int(withdraw)}
    )


def api_get_txs(name, pin):
    return api_get({"action": "get_transactions", "name": name, "pin": pin})


def api_undo_last_n(name, pin, n):
    return api_post({"action": "undo_last_n", "name": name, "pin": pin, "n": int(n)})


def api_update_tx_amount(name, pin, tx_id, new_amount):
    return api_post(
        {"action": "update_transaction_amount", "name": name, "pin": pin,
         "tx_id": tx_id, "new_amount": int(new_amount)}
    )


def api_savings_list(name, pin):
    return api_get({"action": "list_savings", "name": name, "pin": pin})


def api_savings_create(name, pin, principal, weeks):
    return api_post(
        {"action": "savings_create", "name": name, "pin": pin,
         "principal": int(principal), "weeks": int(weeks)}
    )


def api_savings_cancel(name, pin, savings_id):
    return api_post(
        {"action": "savings_cancel", "name": name, "pin": pin,
         "savings_id": savings_id}
    )


def api_process_maturities(name, pin):
    return api_get({"action": "process_maturities", "name": name, "pin": pin})


def api_get_goal(name, pin):
    return api_get({"action": "get_goal", "name": name, "pin": pin})


def api_set_goal(name, pin, goal_amount, goal_date_str):
    return api_post(
        {"action": "set_goal", "name": name, "pin": pin,
         "goal_amount": int(goal_amount), "goal_date": goal_date_str}
    )


# Admin
def api_admin_balances(admin_pin):
    return api_get({"action": "admin_balances", "admin_pin": admin_pin})


def api_admin_reset_pin(admin_pin, name, new_pin):
    return api_post(
        {"action": "admin_reset_pin", "admin_pin": admin_pin,
         "name": name, "new_pin": new_pin}
    )


def api_admin_backup(admin_pin):
    return api_post({"action": "admin_backup", "admin_pin": admin_pin})


def api_admin_bulk_deposit(admin_pin, amount, memo):
    return api_post(
        {"action": "admin_bulk_deposit", "admin_pin": admin_pin,
         "amount": int(amount), "memo": memo}
    )


def api_admin_upsert_template(admin_pin, template_id, label, kind, amount):
    return api_post(
        {"action": "admin_upsert_template", "admin_pin": admin_pin,
         "template_id": template_id, "label": label,
         "kind": kind, "amount": int(amount)}
    )


def api_admin_delete_template(admin_pin, template_id):
    return api_post(
        {"action": "admin_delete_template", "admin_pin": admin_pin,
         "template_id": template_id}
    )


# -------------------------
# Session init
# -------------------------
if "saved_pins" not in st.session_state:
    st.session_state.saved_pins = {}
if "delete_confirm" not in st.session_state:
    st.session_state.delete_confirm = False
if "delete_target" not in st.session_state:
    st.session_state.delete_target = None
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False
if "bulk_confirm" not in st.session_state:
    st.session_state.bulk_confirm = False


# -------------------------
# Sidebar
# -------------------------
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
                st.error("비밀번호는 4자리 숫자여야 해요. (예: 0123)")
            else:
                res = api_create_account(new_name, new_pin)
                if res.get("ok"):
                    toast("계정 생성 완료!")
                    st.session_state.delete_confirm = False
                    st.session_state.pop("new_name", None)
                    st.session_state.pop("new_pin", None)
                    st.rerun()
                else:
                    st.error(res.get("error", "계정 생성 실패"))

    with c2:
        if st.button("삭제"):
            st.session_state.delete_confirm = True
            st.session_state.delete_target = (new_name, new_pin)

    if st.session_state.delete_confirm:
        st.warning("정말로 삭제하시겠습니까?")
        st.caption("※ 삭제하면 해당 계정 탭(통장 내역)도 함께 삭제됩니다.")
        y, n = st.columns(2)
        with y:
            if st.button("예", key="delete_yes"):
                name, pin = st.session_state.delete_target or ("", "")
                name = (name or "").strip()
                pin = (pin or "").strip()
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
                        st.session_state.pop("new_name", None)
                        st.session_state.pop("new_pin", None)
                        st.session_state.saved_pins.pop(name, None)
                        # 삭제된 계정 관련 입력값(위젯 key)도 정리
                        st.session_state.pop(f"pin_{name}", None)
                        st.session_state.pop(f"remember_{name}", None)
                        st.rerun()
                    else:
                        st.error(res.get("error", "삭제 실패"))
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
            res = api_admin_balances(admin_pin)
            if res.get("ok"):
                st.session_state.admin_ok = True
                toast("관리자 모드 ON", icon="🔓")
            else:
                st.session_state.admin_ok = False
                st.error(res.get("error", "관리자 PIN 틀림"))

        if st.session_state.admin_ok:
            st.success("관리자 모드 활성화됨")

            st.subheader("🧩 내역 템플릿 관리")

            tpl_res = api_list_templates()
            templates = tpl_res.get("templates", []) if tpl_res.get("ok") else []

            # ✅ ID는 숨기고, 내역/종류/금액만 표로 보여줌
            if templates:
                show_rows = []
                for t in templates:
                    kind_kr = "입금" if t["kind"] == "deposit" else "출금"
                    show_rows.append({"내역": t["label"], "종류": kind_kr, "금액": int(t["amount"])})
                st.dataframe(pd.DataFrame(show_rows), use_container_width=True, hide_index=True)
            else:
                st.info("템플릿이 아직 없어요. 아래에서 추가해 주세요.")

            st.caption("추가/수정")
            mode = st.radio("작업", ["추가", "수정"], horizontal=True, key="tpl_mode")

            # 수정 모드면 label로 고르게
            edit_id = ""
            edit_label_default = ""
            edit_kind_default = "deposit"
            edit_amount_default = 10

            if mode == "수정" and templates:
                labels = [f"{t['label']} ({'입금' if t['kind']=='deposit' else '출금'} {int(t['amount'])})" for t in templates]
                pick = st.selectbox("수정할 템플릿 선택", list(range(len(templates))), format_func=lambda i: labels[i], key="tpl_pick")
                target = templates[pick]
                edit_id = target["template_id"]
                edit_label_default = target["label"]
                edit_kind_default = target["kind"]
                edit_amount_default = int(target["amount"])

            tcol1, tcol2 = st.columns(2)
            with tcol1:
                tpl_label = st.text_input("내역 이름", value=edit_label_default, key="tpl_label").strip()
                tpl_amount = st.number_input("금액", min_value=1, step=1, value=edit_amount_default, key="tpl_amount")
            with tcol2:
                tpl_kind = st.selectbox("종류", ["deposit", "withdraw"],
                                        index=0 if edit_kind_default == "deposit" else 1, key="tpl_kind")
                st.caption("deposit=입금(보상), withdraw=출금(벌금/구매)")

            if st.button("저장(추가/수정)"):
                if not tpl_label:
                    st.error("내역 이름을 입력해 주세요.")
                else:
                    tid = edit_id if mode == "수정" else ""
                    res = api_admin_upsert_template(admin_pin, tid, tpl_label, tpl_kind, tpl_amount)
                    if res.get("ok"):
                        toast("템플릿 저장 완료!", icon="🧩")
                        st.rerun()
                    else:
                        st.error(res.get("error", "템플릿 저장 실패"))

            st.caption("삭제")
            if templates:
                del_labels = [f"{t['label']} ({'입금' if t['kind']=='deposit' else '출금'} {int(t['amount'])})" for t in templates]
                del_pick = st.selectbox("삭제할 템플릿 선택", list(range(len(templates))),
                                        format_func=lambda i: del_labels[i], key="tpl_del_pick")
                del_id = templates[del_pick]["template_id"]

                if st.button("삭제", key="tpl_del_btn"):
                    st.session_state["tpl_del_confirm"] = True

                if st.session_state.get("tpl_del_confirm", False):
                    st.warning("정말로 삭제하시겠습니까?")
                    y, n = st.columns(2)
                    with y:
                        if st.button("예", key="tpl_del_yes"):
                            res = api_admin_delete_template(admin_pin, del_id)
                            if res.get("ok"):
                                toast("삭제 완료!", icon="🗑️")
                                st.session_state["tpl_del_confirm"] = False
                                st.rerun()
                            else:
                                st.error(res.get("error", "삭제 실패"))
                    with n:
                        if st.button("아니오", key="tpl_del_no"):
                            st.session_state["tpl_del_confirm"] = False
                            st.rerun()

            st.divider()

            st.subheader("🎁 전체 학생 일괄 지급")
            bulk_amount = st.number_input("지급 포인트(+)", min_value=1, step=1, value=10, key="bulk_amount")
            bulk_memo = st.text_input("지급 내역(메모)", value="행사/퀴즈 보상", key="bulk_memo").strip()

            if st.button("지급 실행"):
                st.session_state.bulk_confirm = True

            if st.session_state.bulk_confirm:
                st.warning("정말로 전체 학생에게 일괄 지급하시겠습니까?")
                y, n = st.columns(2)
                with y:
                    if st.button("예", key="bulk_yes"):
                        res = api_admin_bulk_deposit(admin_pin, bulk_amount, bulk_memo)
                        if res.get("ok"):
                            toast(f"일괄 지급 완료! ({res.get('count')}명)", icon="🎉")
                            st.session_state.bulk_confirm = False
                            st.rerun()
                        else:
                            st.error(res.get("error", "일괄 지급 실패"))
                with n:
                    if st.button("아니오", key="bulk_no"):
                        st.session_state.bulk_confirm = False
                        st.rerun()

            st.subheader("💾 백업")
            if st.button("구글시트 백업 만들기"):
                res = api_admin_backup(admin_pin)
                if res.get("ok"):
                    toast(f"백업 생성: {res.get('backup_name')}", icon="💾")
                    st.info("Drive에 백업 파일이 생성되었습니다.")
                else:
                    st.error(res.get("error", "백업 실패"))

            st.subheader("🔧 PIN 재설정")
            target = st.text_input("대상 학생 이름", key="reset_target").strip()
            newp = st.text_input("새 PIN(4자리)", key="reset_pin", type="password").strip()
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
                        st.error(res.get("error", "PIN 변경 실패"))


# -------------------------
# Main: Accounts + Tabs
# -------------------------
accounts_res = api_list_accounts()
if not accounts_res.get("ok"):
    st.error(accounts_res.get("error", "계정 목록을 불러오지 못했어요."))
    st.stop()

accounts = accounts_res.get("accounts", [])
if not accounts:
    st.info("아직 계정이 없어요. 왼쪽에서 계정을 먼저 만들어 주세요.")
    st.stop()

# 템플릿 캐시
tpl_res = api_list_templates()
TEMPLATES = tpl_res.get("templates", []) if tpl_res.get("ok") else []
TEMPLATE_BY_LABEL = {t["label"]: t for t in TEMPLATES}

search = st.text_input("🔎 계정 검색(이름 일부)", key="search").strip()
filtered = [a for a in accounts if (search in a)] if search else accounts
if not filtered:
    st.warning("검색 결과가 없어요.")
    st.stop()

tabs = st.tabs(filtered)


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


for idx, tab in enumerate(tabs):
    name = filtered[idx]
    with tab:
        st.markdown(f"## 🧾 {name} 통장")

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
            continue

        # 만기 자동 반환
        mat = api_process_maturities(name, pin)
        if mat.get("ok") and mat.get("matured_count", 0) > 0:
            st.success(f"🎉 만기 도착! 적금 {mat['matured_count']}건 자동 반환 (+{mat['paid_total']} 포인트)")

        # 거래 내역
        tx_res = api_get_txs(name, pin)
        if not tx_res.get("ok"):
            st.error(tx_res.get("error", "내역을 불러오지 못했어요."))
            continue

        headers = tx_res.get("headers", ["tx_id", "datetime", "memo", "deposit", "withdraw"])
        rows = tx_res.get("rows", [])
        df = build_df(headers, rows)
        balance = int(df["총액"].iloc[-1]) if len(df) else 0
        st.write(f"### 현재 잔액: **{balance} 포인트**")

        st.divider()

        # -------------------------
        # 화면 탭(거래/적금/목표)
        # -------------------------
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

            # 기본값 미리 세팅 (중요: 위젯 만들기 전에!)
            if memo_key not in st.session_state:
                st.session_state[memo_key] = ""
            if dep_key not in st.session_state:
                st.session_state[dep_key] = 0
            if wd_key not in st.session_state:
                st.session_state[wd_key] = 0
            if tpl_sel_key not in st.session_state:
                st.session_state[tpl_sel_key] = "(직접 입력)"

            def on_template_change():
                sel = st.session_state[tpl_sel_key]
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

            labels = ["(직접 입력)"] + [t["label"] for t in TEMPLATES]
            st.selectbox("내역 템플릿", labels, key=tpl_sel_key, on_change=on_template_change)

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
                            st.session_state[memo_key] = ""
                            st.session_state[dep_key] = 0
                            st.session_state[wd_key] = 0
                            st.session_state[tpl_sel_key] = "(직접 입력)"
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
                            st.rerun()
                        else:
                            st.error(res.get("error", "되돌리기 실패"))
                with n:
                    if st.button("아니오", key=f"undo_no_{name}"):
                        st.session_state[f"undo_confirm_{name}"] = False
                        st.rerun()

        # -------------------------
        # 2) 적금 (다시 추가 + 가입 전 미리보기 + 10단위)
        # -------------------------
        with sub2:
            st.subheader("💰 적금")

            # 가입 전 미리보기
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
                    st.rerun()
                else:
                    st.error(res.get("error", "적금 가입 실패"))

            st.divider()

            # 적금 목록
            sres = api_savings_list(name, pin)
            if not sres.get("ok"):
                st.error(sres.get("error", "적금 목록을 불러오지 못했어요."))
            else:
                savings = sres.get("savings", [])
                if not savings:
                    st.info("적금이 아직 없어요.")
                else:
                    # 상태별 표시
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

                            # 해지 버튼(만기 전이면 확인)
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
        # 3) 목표
        # -------------------------
        with sub3:
            st.subheader("🎯 목표 적금(목표 설정/달성률)")

            goal = api_get_goal(name, pin)
            if not goal.get("ok"):
                st.error(goal.get("error", "목표 정보를 불러오지 못했어요."))
            else:
                cur_goal_amt = int(goal.get("goal_amount", 0) or 0)
                cur_goal_date = str(goal.get("goal_date", "") or "")

                c1, c2 = st.columns(2)
                with c1:
                    g_amt = st.number_input("목표 금액", min_value=1, step=1,
                                            value=cur_goal_amt if cur_goal_amt > 0 else 100, key=f"goal_amt_{name}")
                with c2:
                    # 목표 날짜: 저장된 값이 있으면 date로 변환 시도
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
                        st.rerun()
                    else:
                        st.error(res.get("error", "목표 저장 실패"))

                # 달성률 표시
                if cur_goal_amt > 0:
                    pct = min(100, round(balance / cur_goal_amt * 100, 1))
                    st.progress(pct / 100)
                    st.write(f"달성률: **{pct}%**  (현재 {balance} / 목표 {cur_goal_amt})")
                    if cur_goal_date:
                        st.caption(f"목표 날짜: {cur_goal_date}")

        st.divider()

        # -------------------------
        # 통장 내역
        # -------------------------
        st.subheader("📒 통장 내역")
        if len(df) == 0:
            st.info("아직 거래 내역이 없어요.")
        else:
            view = df.rename(columns={"datetime": "날짜-시간", "memo": "내역", "deposit": "입금", "withdraw": "출금"})[
                ["날짜-시간", "내역", "입금", "출금", "총액"]
            ]
            st.dataframe(view, use_container_width=True, hide_index=True)
