import json
import logging
from io import StringIO
import os
import utils.parser

from py_mini_racer import MiniRacer

from configs.dracu_config import DracuConfig
from handlers import BaseHandler, registry
from utils.pdf_builder import build_pdf
from utils import language_map


logger = logging.getLogger(__name__)


@registry(name="dracu", description="Dracu-Riot! Steam版", config_class=DracuConfig)
class DracuHandler(BaseHandler):
    def _handle(self, config: DracuConfig):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        ctx = MiniRacer()
        with open(config.scnchartdata_filepath, mode="r", encoding="UTF-16") as file:
            scnchartdata_json = json.loads(utils.parser.scnchartdata_tjs_to_json(file.read()))
            flag_names = scnchartdata_json["flagkeys"]
            assert flag_names == list(scnchartdata_json["flags"].keys())
            ctx.eval(f"var flags = {json.dumps(scnchartdata_json["flags"])};")
        ctx.eval(f'this["IsTrial"] = {json.dumps(config.is_trial)};')

        ctx.eval(f'this["checkIN"] = {json.dumps(config.adult_enabled and config.check_in)};')
        ctx.eval(f'this["checkOUT"] = {json.dumps(config.adult_enabled and config.check_out)};')
        ctx.eval(f'this["checkMOUTH"] = {json.dumps(config.adult_enabled and config.check_mouth)};')
        ctx.eval(f'this["checkFACE"] = {json.dumps(config.adult_enabled and config.check_face)};')
        ctx.eval(r"""
        var f = {sf: {}};
        function initialize() {
            Object.keys(flags).forEach(key => this[key] = 0);
        }
        function finalize() {
            Object.keys(this).forEach(k => {
                f[k] = this[k];
            });
        }
        function UpdateBranchFlags() {
            initialize();
            for (var character in flags) {
                var conditions = flags[character];
                for (var i = 0; i < conditions.length; i++) {
                    var condition = conditions[i];
                    var selection = condition[0];
                    var selected_id = condition[1];
                    var bonus = condition[2];
                    if (this[selection] === selected_id) {
                        this[character] += bonus;
                    }
                }
            }
            finalize();
        }
        function SetBranchFlags(varName, value) {
            this[varName] = value;
            UpdateBranchFlags();
        }
        function CheckBranchFlags(expr) {
            // js强兼tjs语法
            expr = " " + expr;
            expr = expr.replace(/ \./g, " f.");
            return !!eval(expr);
        }
        function checkAdult() {
        """ + f"    return {json.dumps(config.adult_enabled)};" + """
        }
        initialize();
        finalize();
        """)
        ctx.eval(f'f.sf.clear_miu = {json.dumps(config.clear_miu)};')
        ctx.eval(f'f.sf.clear_azu = {json.dumps(config.clear_azu)};')
        ctx.eval(f'f.sf.clear_rio = {json.dumps(config.clear_rio)};')
        ctx.eval(f'f.sf.clear_eri = {json.dumps(config.clear_eri)};')
        ctx.eval(f'f.sf.clear_nic = {json.dumps(config.clear_nic)};')

        next_storage = config.head_scn
        next_label = config.head_label

        current_storage = config.head_scn
        transcript_buffer = StringIO()
        chapter_count = 0

        def execute_script(expression):
            try:
                return ctx.eval(expression)
            except Exception as exc:
                logger.exception("执行脚本失败：%s / %s：%s", current_storage, next_label, expression)
                raise RuntimeError(
                    f"执行脚本失败：{current_storage} / {next_label}：{expression}"
                ) from exc

        while current_storage:
            if current_storage == "start.ks":
                logger.info("到达线路结尾，线路结束")
                break
            logger.info('准备读取scenes：%s ...', current_storage)
            with open(os.path.join(config.root_dir, f"{current_storage}.json"), mode="r", encoding="UTF-8") as file:
                script_data = json.load(file)
                logger.info("读取场景文件成功：%s", script_data["name"])
                chapter_count += 1
                transcript_buffer.write(f"【第{chapter_count}章】开始\n")
                assert next_storage == script_data["name"]
                scenes_by_label = {
                    scene["label"]: scene
                    for scene in script_data["scenes"]
                }
                while True:
                    if next_label is None:
                        first_scene = min(
                            scenes_by_label.values(),
                            key=lambda scene: int(scene["firstLine"]),
                        )
                        next_label = first_scene["label"]
                    scene = scenes_by_label[next_label]
                    logger.info(
                        "进入场景：%s / %s，行号：%s，标题：%s",
                        current_storage, scene["label"], scene["firstLine"], scene["title"],
                    )
                    if not config.skip_flags:
                        logger.info("当前所有flag加点：")
                        for flag_name in flag_names:
                            logger.info('\t%s: %s', flag_name, ctx.eval(flag_name))
                    assert scene["label"] == next_label

                    for expression, value in scene.get("preevals", []):
                        execute_script(f"{expression} = {json.dumps(value)};")

                    if "selects" in scene.keys():  # 当前scene含有选择块
                        logger.debug('模式：select')
                        choices_by_id = {
                            int(select["selidx"]): select
                            for select in scene["selects"]
                        }
                        available_choice_ids = []
                        for index in sorted(choices_by_id):
                            select = choices_by_id[index]
                            if "eval" in select and not ctx.eval(select["eval"]):
                                logger.info('(X) 第%s个选项【eval不成立，无法选择】：', index)
                            else:
                                available_choice_ids.append(str(index))
                                logger.info('(%s) 第%s个选项：', index, index)
                            logger.info('\t[日文]%s', select["text"])
                            for index_lang, lang in enumerate(("英文", "简中", "繁中"), start=1):
                                logger.info('\t[%s]%s', lang, select["language"][index_lang]["text"])
                            logger.debug('\ttag: %s', select["tag"])
                            if "eval" in select.keys():
                                logger.debug('\teval: %s', select["eval"])
                            logger.debug('\texp: %s', select["exp"])
                            logger.debug('\tstorage: %s', select["storage"])
                            logger.debug('\ttarget: %s', select["target"])
                            if "icon" in select.keys():
                                logger.debug('\ticon: %s', select["icon"])
                        if not available_choice_ids:
                            raise RuntimeError("当前场景没有可用选项")
                        selected_choice_id = None
                        while selected_choice_id not in available_choice_ids:
                            selected_choice_id = input("输入选项序号，按回车键确定：")
                        selected_transition = choices_by_id[int(selected_choice_id)]

                    elif "nexts" in scene.keys():  # 当前scene含有文本块
                        if "texts" in scene.keys():
                            logger.debug('模式：text')
                            for text in scene["texts"]:
                                speaker_name = text[0]
                                dialogue_by_language = text[1]
                                effective_language_id = config.dialogue_language_id if len(dialogue_by_language) > 1 else 0
                                output_speaker_name = dialogue_by_language[effective_language_id][0] or speaker_name
                                output_dialogue_text = dialogue_by_language[effective_language_id][1]
                                output_speaker_prefix = f"【{output_speaker_name}】" if speaker_name else ""
                                transcript_buffer.write(f"{output_speaker_prefix}{output_dialogue_text}\n")
                                if not config.skip_text:
                                    logger.info('原始说话人：%s', speaker_name)
                                    logger.info('[日文]%s: %s', dialogue_by_language[0][0], dialogue_by_language[0][1])
                                    if len(dialogue_by_language) > 1:  # 日文原版或国际中文版的end_of_trial部分无多语言
                                        for index, lang in enumerate(("英文", "简中", "繁中"), start=1):
                                            speaker_alias = dialogue_by_language[index][0]
                                            dialogue_text = dialogue_by_language[index][1]
                                            # text_length = dialogue_multi_lang[index][2]
                                            logger.info('[%s]%s: %s', lang, speaker_alias, dialogue_text)
                                    if not config.skip_confirm:
                                        input("按回车键继续：")
                        else:
                            logger.debug('模式：next')

                        transitions_by_signature = {}
                        for transition in scene["nexts"]:
                            if transition.get("type") == 1:
                                continue
                            signature = utils.generate_next_signature(
                                eval=transition.get("eval"),
                                storage=transition.get("storage"),
                                target=transition.get("target"),
                                type=transition.get("type")
                            )
                            transitions_by_signature[signature] = transition
                        conditional_transitions = []
                        default_transitions = []
                        for transition in transitions_by_signature.values():
                            if "eval" in transition.keys():
                                conditional_transitions.append(transition)
                            else:  # 有些无条件判断的next会同时存在全年龄版与R18版，需要根据是否开启adult来去重
                                if config.adult_enabled:
                                    x_signature = utils.generate_next_signature(
                                        eval=transition.get("eval"),
                                        storage="x_" + transition.get("storage"),
                                        target=transition.get("target"),
                                        type=transition.get("type")
                                    )
                                    if x_signature in transitions_by_signature.keys():
                                        continue
                                elif transition["storage"].startswith("x_"):
                                    non_x_signature = utils.generate_next_signature(
                                        eval=transition.get("eval"),
                                        storage=transition.get("storage").removeprefix("x_"),
                                        target=transition.get("target"),
                                        type=transition.get("type")
                                    )
                                    if non_x_signature in transitions_by_signature.keys():
                                        continue
                                default_transitions.append(transition)
                        for transition in conditional_transitions:
                            condition_met = ctx.eval(transition["eval"])
                            logger.debug("跳转条件：%s，结果：%s", transition["eval"], condition_met)
                            if condition_met:
                                selected_transition = transition
                                break
                        else:
                            if not default_transitions:
                                logger.info("没有可用的下一场景，线路结束")
                                current_storage = None
                                break
                            selected_transition = default_transitions[0]
                            logger.info("无条件判断：")

                    else:
                        raise RuntimeError("?")

                    if selected_transition.get("exp"):
                        result = execute_script(selected_transition["exp"])
                        logger.debug('执行exp成功，返回值：%s', result)
                    next_storage = selected_transition["storage"]
                    next_label = selected_transition.get("target")

                    assert next_storage is not None
                    if next_storage.strip() == "":
                        logger.info('storage为空，回退至当前scenes：%s', current_storage)
                        next_storage = current_storage
                    logger.info("下一场景：%s / %s", next_storage, next_label)
                    if next_storage != current_storage:
                        logger.info("storage发生变化，准备读取下一个scenes...")
                        current_storage = next_storage
                        break
                transcript_buffer.write(f"【第{chapter_count}章】结束\n\n\n\n")
        raw_text = transcript_buffer.getvalue()
        transcript_buffer.close()
        logger.info("正在写入文本：%s", config.output_txt_filepath)
        with open(config.output_txt_filepath, mode="w", encoding="UTF-8") as output_txt:
            output_txt.write(raw_text)
        logger.info('正在生成pdf：%s，耗时可能较长......', config.output_pdf_filepath)
        build_pdf(raw_text=raw_text,
                  language=language_map[config.dialogue_language_id],
                  outfile=config.output_pdf_filepath)
        logger.info("成功生成pdf.")
