import json
import logging
import re
import utils.parser

from py_mini_racer import MiniRacer

from configs.dracu_config import DracuConfig
from handlers import BaseHandler, registry
from models.story_transcript import Chapter, DialogueEntry, DialogueTranslation, StoryTranscript
from utils import logged_input


logger = logging.getLogger(__name__)


@registry(name="dracu", description="Dracu-Riot! Steam版", config_class=DracuConfig)
class DracuHandler(BaseHandler):
    def _handle(self, config: DracuConfig) -> StoryTranscript:
        def execute_expression(expression):
            try:
                return ctx.eval(expression)
            except Exception as exc:
                raise RuntimeError(
                    f"执行expression失败：{current_storage} / {next_label}：{expression}"
                ) from exc

        def execute_evals(evals):
            for item in evals:
                if isinstance(item, str):
                    execute_expression(item)
                else:
                    expression, value = item
                    execute_expression(f"{expression} = {json.dumps(value)};")

        def resolve_text(text):
            def replace_expression(match):
                expression = match[1]
                # TJS 的 $数字 是字符字面量，例如 $38 表示 &。
                if re.fullmatch(r"\$\d+", expression):
                    return chr(int(expression[1:]))
                return execute_expression(f"String(({expression}))")
            return re.sub(r"\$\{([^{}]+)\}", replace_expression, text)

        # 初始化本次剧本记录。
        transcript = StoryTranscript()
        dialogue_text_index = config.dialogue_text_variant.value
        with MiniRacer() as ctx:
            # 加载角色加点规则，供后续分支计算使用。
            branch_flags = utils.parser.load_branch_flags(config.scnchartdata_filepath)
            flag_names = list(branch_flags)
            ctx.eval(f"var flags = {json.dumps(branch_flags)};")

            # 将体验版和成人选项开关注入脚本运行时。
            runtime_options = {
                "IsTrial": config.is_trial,
                "checkIN": config.adult_enabled and config.check_in,
                "checkOUT": config.adult_enabled and config.check_out,
                "checkMOUTH": config.adult_enabled and config.check_mouth,
                "checkFACE": config.adult_enabled and config.check_face,
            }
            ctx.eval(f"Object.assign(this, {json.dumps(runtime_options)});")

            # 文本中的取词表达式使用配置词表和当前 f.dick 状态。
            ctx.eval(f"""
            function _get_dick_word(type, lang) {{
                var flag = f.dick;
                if (flag >= 8) flag >>= 3;
                var idx = (flag >= 4) ? 2 : (flag >= 2) ? 1 : 0;
                return ({json.dumps(config.dick_word_table)})[lang][type][idx];
            }}
            """)

            ctx.eval(f"function checkAdult() {{ return {json.dumps(config.adult_enabled)}; }}")

            # 定义flag加点计算函数，并初始化脚本状态。
            ctx.eval(r"""
            var sf = {};
            // f 是全局对象的代理，属性读写和删除共享同一份状态。
            var f = new Proxy(globalThis, {});
            function UpdateBranchFlags() {
                for (const [flagName, conditions] of Object.entries(flags)) {
                    // 保留全局字段，避免裸名称访问报错；未命中规则时值仍未定义。
                    f[flagName] = undefined;
                    for (const [selection, selectedId, bonus] of conditions) {
                        if (f[selection] == selectedId) {
                            f[flagName] = (f[flagName] ?? 0) + bonus;
                        }
                    }
                }
            }
            function SetBranchFlags(varName, value) {
                f[varName] = value;
                sf[varName] = value;
                UpdateBranchFlags();
            }
            function CheckBranchFlags(expression) {
                UpdateBranchFlags();
                // 去掉 TJS 省略对象前缀的前导点，直接访问全局字段。
                const normalized = expression.replace(
                    /(^|[^\w$.])\.(?=[A-Za-z_$])/g,
                    "$1"
                );
                return eval(normalized);
            }
            UpdateBranchFlags();
            """)

            # DR独有：初始化各角色线路的通关状态。
            clear_flags = {
                "clear_miu": config.clear_miu,
                "clear_azu": config.clear_azu,
                "clear_rio": config.clear_rio,
                "clear_eri": config.clear_eri,
                "clear_nic": config.clear_nic,
            }
            ctx.eval(f"Object.assign(sf, {json.dumps(clear_flags)});")

            # 设置流程起点。
            next_storage = config.head_scn
            next_label = config.head_label

            current_storage = config.head_scn

            # 文件循环：加载脚本、创建章节并建立标签索引。
            while current_storage:
                if current_storage == "start.ks":
                    logger.info("到达线路结尾，线路结束")
                    break
                logger.info('准备读取场景文件：%s ...', current_storage)
                with (config.root_dir / f"{current_storage}.json").open(mode="r", encoding="UTF-8") as file:
                    script_data = json.load(file)
                if not transcript.chapters:
                    transcript.supported_languages.extend(script_data.get("languages", []))
                logger.info("已读取场景文件：%s", script_data["name"])
                chapter = Chapter(storage=current_storage)
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
                        "已进入场景：%s / %s",
                        current_storage, scene["label"],
                    )
                    if not config.skip_flags:
                        logger.info("当前所有flag加点：")
                        for flag_name in flag_names:
                            logger.info('\t%s: %s', flag_name, ctx.eval(flag_name))

                    # 执行preevals。
                    execute_evals(scene.get("preevals", []))

                    # 选择块：筛选可用选项，等待用户选择。
                    if "selects" in scene:
                        logger.info('当前状态机模式：select')
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
                            logger.info('\t[%s]%s', transcript.supported_languages[0].upper(), choice["text"])
                            for language, translation in zip(transcript.supported_languages[1:], choice["language"][1:]):
                                logger.info('\t[%s]%s', language.upper(), translation["text"])
                            for field, value in choice.items():
                                if field not in {"selidx", "text", "language"}:
                                    logger.debug("\t%s: %s", field, value)
                        if not available_choices:
                            raise RuntimeError("当前场景没有可用选项")
                        selected_choice_id = None
                        while selected_choice_id not in available_choices:
                            selected_choice_id = logged_input(logger, "输入选项序号（括号内数字），按回车键确定：")
                        selected_transition = available_choices[selected_choice_id]

                        # 选择完成后执行场景末尾的 postevals。
                        execute_evals(scene.get("postevals", []))

                    # 自动跳转块：先收集正文，再选择下一位置。
                    elif "nexts" in scene:
                        if "texts" in scene:
                            logger.info('当前状态机模式：text')
                            for text in scene["texts"]:
                                speaker_name = text[0]
                                dialogue_by_language = text[1]
                                translations = {
                                    language: DialogueTranslation(
                                        speaker_alias=dialogue[0],
                                        text=resolve_text(
                                            dialogue[dialogue_text_index]
                                            if len(dialogue) > dialogue_text_index else dialogue[1]
                                        ),
                                    )
                                    for language, dialogue in zip(transcript.supported_languages, dialogue_by_language)
                                }
                                chapter.entries.append(DialogueEntry(
                                    original_speaker=speaker_name,
                                    translations=translations,
                                ))
                                if not config.skip_text:
                                    logger.info("原始说话人：%s", speaker_name)
                                    for language, translation in translations.items():
                                        logger.info("[%s]%s: %s", language.upper(), translation.speaker_alias, translation.text)
                                    if not config.skip_confirm:
                                        logged_input(logger, "按回车键继续：")
                        else:
                            logger.info('当前状态机模式：next')

                        # 正文处理完成后执行 postevals，再判断跳转条件。
                        execute_evals(scene.get("postevals", []))

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

                            # 暂停按 x_ 前缀配对筛选，成人版选择交由剧本中的跳转条件处理。
                            # transition_storage = transition["storage"]
                            # if config.adult_enabled:
                            #     counterpart_storage = "x_" + transition_storage
                            # elif transition_storage.startswith("x_"):
                            #     counterpart_storage = transition_storage.removeprefix("x_")
                            # else:
                            #     counterpart_storage = None
                            # if counterpart_storage is not None:
                            #     counterpart_signature = (
                            #         transition.get("eval"),
                            #         counterpart_storage,
                            #         transition.get("target"),
                            #         transition.get("type"),
                            #     )
                            #     if counterpart_signature in transitions_by_signature:
                            #         continue
                            if default_transition is None:
                                default_transition = transition

                        # 条件均不成立时使用默认项；没有默认项则结束。
                        if selected_transition is None:
                            selected_transition = default_transition
                            if selected_transition is None:
                                logger.info("没有可用的下一场景，线路结束\n")
                                current_storage = None
                                break
                            logger.info("不存在可用的条件跳转，使用缺省跳转...")

                    else:
                        raise RuntimeError("?")

                    # 执行选中项的 exp，再更新位置或切换文件。
                    if selected_transition.get("exp"):
                        result = execute_expression(selected_transition["exp"])
                        logger.debug('执行exp成功，返回值：%s', result)
                    next_storage = selected_transition["storage"]
                    next_label = selected_transition.get("target")

                    assert next_storage is not None
                    if next_storage.strip() == "":
                        logger.info('storage为空，回退至当前scenes：%s', current_storage)
                        next_storage = current_storage
                    logger.info("准备进入下一个场景：%s / %s\n", next_storage, next_label)
                    if next_storage != current_storage:
                        logger.info("storage发生变化，准备读取下一个场景文件...")
                        current_storage = next_storage
                        break

                # 当前文件流程结束后，将完整章节加入剧本记录。
                transcript.chapters.append(chapter)

        # 返回剧情对象供导出复用。
        return transcript
