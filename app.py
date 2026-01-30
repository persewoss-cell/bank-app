import streamlit as st
import requests

WEBAPP_URL = "https://script.google.com/macros/s/AKfycbx4aS0JiOp-P2_AO5uh_vTbkXzDXzLiDa067a9cr7o/dev"

st.title("구글시트 기록 테스트")

name = st.text_input("이름")
memo = st.text_input("내역")
deposit = st.number_input("입금", min_value=0, step=1, value=0)
withdraw = st.number_input("출금", min_value=0, step=1, value=0)
total = st.number_input("총액", min_value=0, step=1, value=0)

if st.button("구글시트에 저장"):
    payload = {
        "name": name,
        "memo": memo,
        "deposit": int(deposit),
        "withdraw": int(withdraw),
        "total": int(total)
    }

    r = requests.post(WEBAPP_URL, json=payload)
    st.success("전송 완료! 구글시트 확인해보세요.")
