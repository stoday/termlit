import termlit

termlit.welcome(
    title="Welcome~",
    subtitle="version 1.0.0",
    description="This is a note",
)

while True:
    prompt = termlit.input("User question: ")

    if prompt.lower() in {"quit", "exit"}:
        termlit.goodbye("Goodbye! See you next time")
        break
    elif prompt.strip() == "upload":
        raw_input = termlit.input("Enter file paths (comma separated): ")
        paths = [item.strip() for item in raw_input.split(",") if item.strip()]
        if not paths:
            termlit.write("No file paths provided, cancelled.")
            continue
        target = paths if len(paths) > 1 else paths[0]
        upload_file_new_name = termlit.upload_file(target, show_progress=True, replace=True)
        termlit.write('***' + str(upload_file_new_name))
        termlit.write("File upload completed!")
        continue
    elif prompt.strip() == "download":
        remote_paths = termlit.input("Enter server file paths (comma separated): ")
        targets = [item.strip() for item in remote_paths.split(",") if item.strip()]
        if not targets:
            termlit.write("No file paths provided, cancelled.")
            continue
        # method = termlit.input("Select download method (scp/http, default scp): ").strip().lower()
        # method = method or "scp"
        # base_dir = termlit.input(
        #     "Specify server folder (e.g. upload_files), press Enter to skip: "
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
            termlit.write("Please open the following URL in browser to download:")
            # if method == "http":
            #     termlit.write("Please open the following URL in browser to download:")
            # else:
            #     termlit.write("Run the following command in local terminal to download:")
            termlit.write(cmd)
        except (ValueError, FileNotFoundError, IsADirectoryError) as exc:
            termlit.write(f"Failed to generate download command: {exc}")
        continue
    with termlit.spinner("dots", "Processing your request..."):
        response = termlit.post(
            url="https://httpbin.org/post",
            json={"question": prompt + '-aaa'},
            log=False,
        )
        
    termlit.write('Answer: ' + str(response.json()))
