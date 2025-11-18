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
    elif prompt.strip() == "upload":
        raw_input = termlit.input("請輸入檔案路徑 (可用逗號分隔多個): ")
        paths = [item.strip() for item in raw_input.split(",") if item.strip()]
        if not paths:
            termlit.write("未提供任何檔案路徑，已取消。")
            continue
        target = paths if len(paths) > 1 else paths[0]
        upload_file_new_name = termlit.upload_file(target, show_progress=True)
        termlit.write('***' + str(upload_file_new_name))
        termlit.write("檔案已上傳完成！")
        continue
    elif prompt.strip() == "download":
        remote_paths = termlit.input("請輸入伺服器檔案路徑 (可用逗號分隔): ")
        targets = [item.strip() for item in remote_paths.split(",") if item.strip()]
        if not targets:
            termlit.write("未提供任何檔案路徑，已取消。")
            continue
        # method = termlit.input("選擇下載方式 (scp/http，預設 scp): ").strip().lower()
        # method = method or "scp"
        # base_dir = termlit.input(
        #     "如需指定伺服器資料夾 (例: upload_files)，請輸入 (按 Enter 略過): "
        # ).strip()
        # cmd_kwargs = {}
        # if base_dir:
        #     cmd_kwargs["source_dir"] = base_dir
        source_dir = "upload_files"
        try:
            cmd = termlit.download_cmd(
                targets if len(targets) > 1 else targets[0],
                # type=method,
                source_dir=source_dir,
            )
            termlit.write("請在瀏覽器開啟以下網址進行下載:")
            # if method == "http":
            #     termlit.write("請在瀏覽器開啟以下網址進行下載:")
            # else:
            #     termlit.write("請在本機終端執行以下指令進行下載:")
            termlit.write(cmd)
        except (ValueError, FileNotFoundError, IsADirectoryError) as exc:
            termlit.write(f"產生下載指令失敗: {exc}")
        continue
    with termlit.spinner("dots", "正在處理您的問題..."):
        response = termlit.post(
            url="https://httpbin.org/post",
            json={"question": prompt + '-aaa'},
            log=False,
        )
        
    termlit.write('回答: ' + str(response.json()))
