import os

from dotenv import load_dotenv
import streamlit as st
import requests

load_dotenv()

API_URL = os.environ["API_URL"]

st.title("Bedrock RAG Chat")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("質問を入力してください"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("回答を生成中..."):
            resp = requests.post(API_URL, json={"query": prompt}, timeout=30)
            data = resp.json()

            answer = data.get("answer", "回答を取得できませんでした。")
            st.markdown(answer)

            citations = data.get("citations", [])
            if citations:
                with st.expander("参照ソース"):
                    for i, c in enumerate(citations, 1):
                        st.markdown(f"**[{i}]** {c['source']}")
                        st.caption(c["text"][:300] + "...")

    st.session_state.messages.append({"role": "assistant", "content": answer})
