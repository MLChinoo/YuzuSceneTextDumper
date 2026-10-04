import json
import logging
import os
import utils.parser

from py_mini_racer import MiniRacer

from configs.dracu_config import DracuConfig
from handlers import BaseHandler, registry
from models.story_transcript import DialogueEntry, DialogueTranslation, StoryTranscript


logger = logging.getLogger(__name__)


@registry(name="dracu", description="Dracu-Riot! Steam版", config_class=DracuConfig)
class DracuHandler(BaseHandler):
    def _handle(self, config: DracuConfig) -> StoryTranscript:
        def execute(expression):
            try:
                return ctx.eval(expression)
            except Exception as exc:
                logger.exception("执行脚本失败：%s / %s：%s", current_storage, next_label, expression)
                raise RuntimeError(
                    f"执行脚本失败：{current_storage} / {next_label}：{expression}"
                ) from exc

        # 初始化日志和本次剧情记录。
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        transcript = StoryTranscript(supported_languages=["jp"])
        with MiniRacer() as ctx:
            # 加载角色加点规则，供后续分支计算使用。
            with open(config.scnchartdata_filepath, mode="r", encoding="UTF-16") as file:
                scnchartdata_json = json.loads(utils.parser.scnchartdata_tjs_to_json(file.read()))
                flag_names = scnchartdata_json["flagkeys"]
                assert flag_names == list(scnchartdata_json["flags"].keys())
                ctx.eval(f"var flags = {json.dumps(scnchartdata_json["flags"])};")

            # 将体验版和成人选项开关注入脚本运行时。
            runtime_options = {
                "IsTrial": config.is_trial,
                "checkIN": config.adult_enabled and config.check_in,
                "checkOUT": config.adult_enabled and config.check_out,
                "checkMOUTH": config.adult_enabled and config.check_mouth,
                "checkFACE": config.adult_enabled and config.check_face,
            }
            ctx.eval(f"Object.assign(this, {json.dumps(runtime_options)});")

            # 定义分支计算函数，并初始化脚本状态。
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

            # DR独有：初始化各角色线路的通关状态。
            clear_flags = {
                "clear_miu": config.clear_miu,
                "clear_azu": config.clear_azu,
                "clear_rio": config.clear_rio,
                "clear_eri": config.clear_eri,
                "clear_nic": config.clear_nic,
            }
            ctx.eval(f"Object.assign(f.sf, {json.dumps(clear_flags)});")

            # 设置流程起点。
            next_storage = config.head_scn
            next_label = config.head_label

            current_storage = config.head_scn

            # 文件循环：加载脚本、创建章节并建立标签索引。
            while current_storage:
                if current_storage == "start.ks":
                    logger.info("到达线路结尾，线路结束")
                    break
                logger.info('准备读取scenes：%s ...', current_storage)
                with open(os.path.join(config.root_dir, f"{current_storage}.json"), mode="r", encoding="UTF-8") as file:
                    script_data = json.load(file)
                # 仅从初始脚本读取语言声明，保留原始语言代码。
                if not transcript.chapters:
                    transcript.supported_languages.extend(script_data.get("languages", []))
                logger.info("读取场景文件成功：%s", script_data["name"])
                chapter = transcript.add_chapter(current_storage)
                assert next_storage == script_data["name"]
                scenes_by_label = {
                    scene["label"]: scene
                    for scene in script_data["scenes"]
                }

                # 场景循环：按标签推进，未指定标签时进入最早场景。
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

                    # 先执行场景进入赋值，再处理选择和跳转。
                    for expression, value in scene.get("preevals", []):
                        execute(f"{expression} = {json.dumps(value)};")

                    # 选择块：筛选可用选项，等待用户选择。
                    if "selects" in scene:
                        logger.debug('模式：select')
                        choices_by_id = {
                            int(choice["selidx"]): choice
                            for choice in scene["selects"]
                        }
                        available_choices = {}
                        for choice_id in sorted(choices_by_id):
                            choice = choices_by_id[choice_id]
                            if "eval" in choice and not ctx.eval(choice["eval"]):
                                logger.info('(X) 第%s个选项【eval不成立，无法选择】：', choice_id)
                            else:
                                available_choices[str(choice_id)] = choice
                                logger.info('(%s) 第%s个选项：', choice_id, choice_id)
                            logger.info('\t[日文]%s', choice["text"])
                            for language_name, translation in zip(("英文", "简中", "繁中"), choice["language"][1:]):
                                logger.info('\t[%s]%s', language_name, translation["text"])
                            for field, value in choice.items():
                                if field not in {"selidx", "text", "language"}:
                                    logger.debug("\t%s: %s", field, value)
                        if not available_choices:
                            raise RuntimeError("当前场景没有可用选项")
                        selected_choice_id = None
                        while selected_choice_id not in available_choices:
                            selected_choice_id = input("输入选项序号，按回车键确定：")
                        selected_transition = available_choices[selected_choice_id]

                    # 自动跳转块：先收集正文，再选择下一位置。
                    elif "nexts" in scene:
                        if "texts" in scene:
                            # 原样保存全部语言；别名补全交给 exporter。
                            logger.debug('模式：text')
                            for text in scene["texts"]:
                                speaker_name = text[0]
                                dialogue_by_language = text[1]
                                translations = {
                                    language: DialogueTranslation(
                                        speaker_alias=dialogue[0],
                                        text=dialogue[1],
                                    )
                                    for language, dialogue in zip(transcript.supported_languages, dialogue_by_language)
                                }
                                chapter.entries.append(DialogueEntry(
                                    original_speaker=speaker_name,
                                    translations=translations,
                                ))
                                if not config.skip_text:
                                    logger.info("原始说话人：%s", speaker_name)
                                    for language_name, dialogue in zip(("日文", "英文", "简中", "繁中"), dialogue_by_language):
                                        speaker_alias, dialogue_text = dialogue[:2]
                                        logger.info("[%s]%s: %s", language_name, speaker_alias, dialogue_text)
                                    if not config.skip_confirm:
                                        input("按回车键继续：")
                        else:
                            logger.debug('模式：next')

                        # 整理候选：过滤 type == 1，并按跳转签名去重。
                        transitions_by_signature = {}
                        for transition in scene["nexts"]:
                            if transition.get("type") == 1:
                                continue
                            signature = (
                                transition.get("eval"),
                                transition.get("storage"),
                                transition.get("target"),
                                transition.get("type"),
                            )
                            transitions_by_signature[signature] = transition

                        # 首个成立的条件优先，无条件项作为默认跳转。
                        selected_transition = None
                        default_transition = None
                        for transition in transitions_by_signature.values():
                            if "eval" in transition:
                                condition_met = ctx.eval(transition["eval"])
                                logger.debug("跳转条件：%s，结果：%s", transition["eval"], condition_met)
                                if condition_met:
                                    selected_transition = transition
                                    break
                                continue

                            # 两个版本同时存在时，根据成人开关保留对应版本。
                            transition_storage = transition["storage"]
                            if config.adult_enabled:
                                counterpart_storage = "x_" + transition_storage
                            elif transition_storage.startswith("x_"):
                                counterpart_storage = transition_storage.removeprefix("x_")
                            else:
                                counterpart_storage = None
                            if counterpart_storage is not None:
                                counterpart_signature = (
                                    transition.get("eval"),
                                    counterpart_storage,
                                    transition.get("target"),
                                    transition.get("type"),
                                )
                                if counterpart_signature in transitions_by_signature:
                                    continue
                            if default_transition is None:
                                default_transition = transition

                        # 条件均不成立时使用默认项；没有默认项则结束。
                        if selected_transition is None:
                            selected_transition = default_transition
                            if selected_transition is None:
                                logger.info("没有可用的下一场景，线路结束")
                                current_storage = None
                                break
                            logger.info("无条件判断：")

                    else:
                        raise RuntimeError("?")

                    # 执行选中项的 exp，再更新位置或切换文件。
                    if selected_transition.get("exp"):
                        result = execute(selected_transition["exp"])
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

        # 返回剧情对象供导出复用。
        return transcript
