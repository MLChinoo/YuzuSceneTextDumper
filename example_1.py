from handlers import Handlers, HandlerMeta
from exporters import Exporters

if __name__ == "__main__":
    print("\n选择游戏：")
    handler_names = list(Handlers.keys())

    for index, name in enumerate(handler_names):
        desc = Handlers[name].description
        print(f"\t【{index}】{name} - {desc}")

    selected_id = None
    while selected_id not in (str(i) for i in range(len(handler_names))):
        selected_id = input("请输入编号：")

    selected_name = handler_names[int(selected_id)]

    root_dir = input("root_dir: ")
    scnchartdata_filepath = input("scnchartdata_filepath: ")

    handler: HandlerMeta = Handlers[selected_name]
    handler_config = handler.build_config(
        root_dir=root_dir,
        scnchartdata_filepath=scnchartdata_filepath
    )
    transcript = handler.clazz().handle(handler_config)
    if transcript is not None:
        Exporters["txt"].clazz().export(
            transcript, "output/output.txt", language="sc",
        )
        # 按需启用 PDF 导出：
        # Exporters["pdf"].clazz().export(
        #     transcript, "output/output.pdf", language="sc",
        # )

