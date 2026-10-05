import re

with open('ui/static/js/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# I will just write a wrapper function that handles SSE logic and update app.js to use it.
# To be safe, I'll just append it to the top.

wrapper = """
function setupSSE(endpoint, prefix, onResultCb) {
  let evt = new EventSource(endpoint);
  evt.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if(data.type === 'log') {
      window[prefix + 'AddLog'](data);
    } else if (data.type === 'result') {
      if(data.success) window[prefix + 'Ok']++; else window[prefix + 'Fail']++;
      window[prefix + 'UpdateStats']();
      if(data.success) window[prefix + 'LoadAccounts']();
      if(onResultCb) onResultCb(data);
    } else if (data.type === 'done') {
      window[prefix + 'IsRunning'] = false;
      window[prefix + 'SetUI'](false);
      evt.close();
      showToast('✅', 'Xong!');
      window[prefix + 'LoadAccounts']();
    } else if (data.type === 'stopped') {
      window[prefix + 'IsRunning'] = false;
      window[prefix + 'SetUI'](false);
      evt.close();
      showToast('⏹', 'Đã dừng.');
    } else if (data.type === 'pending_count_update') {
      if(window[prefix + 'LoadPendingLinkCount']) window[prefix + 'LoadPendingLinkCount']();
      window[prefix + 'LoadAccounts']();
    }
  };
  return evt;
}
"""

if "function setupSSE" not in content:
    content = wrapper + "\n" + content
    
    # Replace ccStartSSE
    cc_sse = """function ccStartSSE(){
  if(ccEvt)ccEvt.close(); ccEvt = setupSSE('/api/capcut/task/stream', 'cc', () => { ccLoadHotmailCount(); });
}"""
    content = re.sub(r'function ccStartSSE\(\)\{.*?\n\}', cc_sse, content, flags=re.DOTALL)
    
    # Replace hfStartSSE
    hf_sse = """function hfStartSSE(){
  if(hfEvt)hfEvt.close(); hfEvt = setupSSE('/api/higgsfield/task/stream', 'hf');
}"""
    content = re.sub(r'function hfStartSSE\(\)\{.*?\n\}', hf_sse, content, flags=re.DOTALL)
    
    # Replace gptStartSSE
    gpt_sse = """function gptStartSSE(){
  if(gptEvt)gptEvt.close(); gptEvt = setupSSE('/api/gpt/task/stream', 'gpt');
}"""
    content = re.sub(r'function gptStartSSE\(\)\{.*?\n\}', gpt_sse, content, flags=re.DOTALL)

    with open('ui/static/js/app.js', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Patched app.js successfully!")
else:
    print("Already patched app.js")
