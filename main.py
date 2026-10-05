import logging
from pathlib import Path

from handlers import Handlers, HandlerMeta
from exporters import Exporters
from utils import logged_input


logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("选择游戏：")
    handler_names = list(Handlers.keys())

    for index, name in enumerate(handler_names):
        desc = Handlers[name].description
        logger.info("\t【%s】%s - %s", index, name, desc)

    selected_id = None
    while selected_id not in (str(i) for i in range(len(handler_names))):
        selected_id = logged_input(logger, "请输入编号：")

    selected_name = handler_names[int(selected_id)]

    root_dir = Path(logged_input(logger, "存放反编译后的.ks.json文件夹路径: ").removeprefix('"').removesuffix('"'))
    scnchartdata_filepath = Path(logged_input(logger, "scnchartdata.tjs文件路径: ").removeprefix('"').removesuffix('"'))

    root_dir = Path(r"C:\Users\MLChinoo\Desktop\yuzu_scns\dracu_steam")
    scnchartdata_filepath = Path(r"C:\Users\MLChinoo\Desktop\yuzu_scns\x_scnchartdata.tjs")

    handler: HandlerMeta = Handlers[selected_name]
    handler_config = handler.build_config(
        root_dir=root_dir,
        scnchartdata_filepath=scnchartdata_filepath
    )
    transcript = handler.clazz().handle(handler_config)
    if transcript is not None:
        Exporters["txt"].clazz().export(
            transcript, "output/output.txt", language="cn",
        )
        # 按需启用 PDF 导出：
        # Exporters["pdf"].clazz().export(
        #     transcript, "output/output.pdf", language="cn",
        # )
