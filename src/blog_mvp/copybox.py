"""Clipboard component with a selection fallback; escape all untrusted content."""
import html


def copy_html(text, label):
    escaped = html.escape(text, quote=True)
    return f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<style>
body {{font-family:system-ui;margin:0}} button {{padding:12px 20px;border:0;
border-radius:8px;background:#176b4d;color:white;font-size:16px;cursor:pointer}}
textarea {{width:98%;height:70px;margin-top:10px;box-sizing:border-box}}
small {{display:block;margin-top:6px}}
</style>
<button id="copy">{html.escape(label)}</button>
<small id="status" role="status">버튼을 누르면 복사됩니다. 실패하면 아래 글을 길게 눌러 복사하세요.</small>
<textarea id="text" readonly aria-label="{html.escape(label, quote=True)}">{escaped}</textarea>
<script>
document.getElementById('copy').onclick = async () => {{
 const box = document.getElementById('text');
 try {{
   await navigator.clipboard.writeText(box.value);
   document.getElementById('status').textContent = '복사했습니다. 블로그 편집기에 붙여넣으세요.';
 }} catch (e) {{
   box.focus(); box.select(); box.setSelectionRange(0, box.value.length);
   let ok = false;
   try {{ ok = document.execCommand('copy'); }} catch (e) {{}}
   document.getElementById('status').textContent = ok ? '복사했습니다.' : '선택된 글을 길게 눌러 복사하세요.';
 }}
}};
</script></html>"""
