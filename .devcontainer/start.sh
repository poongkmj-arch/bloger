#!/usr/bin/env bash
set -eu
if ! python -c 'import streamlit, blog_mvp, openai' >/dev/null 2>&1; then
  python -m pip install -e '.[dashboard]'
fi
if ! python -c 'import socket; s=socket.create_connection(("127.0.0.1",8501),1); s.close()' >/dev/null 2>&1; then
  mkdir -p data
  nohup python -m streamlit run app.py --server.headless true >data/streamlit.log 2>&1 </dev/null &
fi
