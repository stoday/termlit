import termlit

termlit.welcome(
    title="Welcome~",
    subtitle="version 1.0.0",
    description="This is a note",
)

while True:
    prompt = termlit.input("使用者提問: ")

    if prompt.lower() in {"quit", "exit"}:
        termlit.goodbye("再見！期待下次")
        break
    with termlit.spinner("dots", "正在處理您的問題..."):
        response = termlit.post(
            url="https://httpbin.org/post",
            json={"question": prompt},
            log=False,
        )
        
    termlit.write('回答: ' + str(response.json()))
