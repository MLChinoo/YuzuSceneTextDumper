import json
import traceback
import utils.parser

from py_mini_racer import MiniRacer

from configs.senren_config import SenrenConfig
from handlers import BaseHandler, registry
from utils.pdf_builder import build_pdf
from utils import language_map


@registry(name="senren", description="千恋＊万花 Steam版", config_class=SenrenConfig)
class SenrenHandler(BaseHandler):
    def _handle(self, config: SenrenConfig):
        ctx = MiniRacer()
        branch_flags = utils.parser.load_branch_flags(config.scnchartdata_filepath)
        flagkeys = list(branch_flags)
        ctx.eval(f"var flags = {json.dumps(branch_flags)};")
        ctx.eval(f'this["checkAnyClear"] = {json.dumps(config.check_any_clear)};')
        ctx.eval(f'this["checkIN"] = {json.dumps(config.adult_enabled and config.check_in)};')
        ctx.eval(f'this["checkOUT"] = {json.dumps(config.adult_enabled and config.check_out)};')
        ctx.eval(f'this["checkMOUTH"] = {json.dumps(config.adult_enabled and config.check_mouth)};')
        ctx.eval(f'this["checkFACE"] = {json.dumps(config.adult_enabled and config.check_face)};')
        ctx.eval(r"""
        var f = {};
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
        initialize();
        finalize();
        """)

        storage = config.head_scn
        target = config.head_label

        current_scn = config.head_scn
        output_txt = open(config.output_txt_filepath, mode="w+", encoding="UTF-8")
        chapter_count = 0
        while current_scn:
            print()
            if current_scn == "start.ks":
                print("到达线路结尾，线路结束")
                print()
                break
            print(f"准备读取scenes：{current_scn} ...")
            with (config.root_dir / f"{current_scn}.json").open(mode="r", encoding="UTF-8") as file:
                loaded_json = json.load(file)
                print(f"读取scenes：{current_scn} 成功")
                print(f"\tname: {loaded_json["name"]}")
                chapter_count += 1
                output_txt.write(f"【第{chapter_count}章】开始\n")
                # input("[DEBUG]回车继续")
                assert storage == loaded_json["name"]
                print("————————————————————")
                scenes_map = {}
                min_first_line = 2147483647
                for scene_cached in loaded_json["scenes"]:
                    scenes_map[scene_cached["label"]] = scene_cached
                    min_first_line = current_first_line if (current_first_line := int(scene_cached["firstLine"])) < min_first_line else min_first_line
                if target is None:
                    for scene in scenes_map.values():
                        if scene["firstLine"] == min_first_line:
                            target = scene["label"]
                while True:
                    scene = scenes_map[target]
                    print("当前scene：")
                    print(f"\tfirstLine: {scene["firstLine"]}")
                    print(f"\tlabel: {scene["label"]}（应与上一个target一致）")
                    print(f"\ttitle: {scene["title"]}")
                    print()
                    if not config.skip_flags:
                        print("当前所有flag加点：")
                        for flagkey in flagkeys:
                            print(f"\t{flagkey}: {ctx.eval(flagkey)}")
                        print()
                    assert scene["label"] == target

                    for expression, value in scene.get("preevals", []):
                        ctx.eval(f"{expression} = {json.dumps(value)};")

                    if "selects" in scene.keys():  # 当前scene含有选择块
                        print(f"模式：select")
                        selects_map = {}
                        for select_cached in scene["selects"]:
                            selects_map[int(select_cached["selidx"])] = select_cached
                        valid_indexes = list(selects_map.keys())
                        valid_indexes.sort()
                        valid_indexes = list(str(_) for _ in valid_indexes)
                        for index in valid_indexes.copy():
                            select = selects_map[index := int(index)]
                            if "eval" in select.keys() and not ctx.eval(select["eval"]):
                                valid_indexes.remove(str(index))
                                print(f"(X) 第{index}个选项【eval不成立，无法选择】：")
                            else:
                                print(f"({index}) 第{index}个选项：")
                            print(f"\t[日文]{select["text"]}")
                            for index_lang, lang in enumerate(("英文", "简中", "繁中"), start=1):
                                print(f"\t[{lang}]{select["language"][index_lang]["text"]}")
                            print(f"\ttag: {select["tag"]}")
                            if "eval" in select.keys():
                                print(f"\teval: {select["eval"]}")
                            print(f"\texp: {select["exp"]}")
                            print(f"\tstorage: {select["storage"]}")
                            print(f"\ttarget: {select["target"]}")
                        selected_id = "0d000721"
                        while selected_id not in valid_indexes :
                            selected_id = input("输入选项序号，按回车键确定：")
                        selected = scene["selects"][int(selected_id)]
                        try:
                            rtn = ctx.eval(selected["exp"])
                            print(f"执行exp成功，返回值：{rtn}")
                        except Exception:
                            print(f"执行exp失败，异常：")
                            traceback.print_exc()
                            print("可能影响后续路线走向！！")
                        finally:
                            print()
                            storage = selected["storage"]
                            target = selected["target"]

                    elif "nexts" in scene.keys():  # 当前scene含有文本块
                        if "texts" in scene.keys():
                            print(f"模式：text")
                            for text in scene["texts"]:
                                speaker_name = text[0]
                                dialogue_multi_lang = text[2]
                                output_language_id = config.dialogue_language_id if len(dialogue_multi_lang) > 1 else 0
                                output_speaker_name = dialogue_multi_lang[output_language_id][0] or speaker_name
                                output_dialogue_text = dialogue_multi_lang[output_language_id][1]
                                output_speaker_prefix = f"【{output_speaker_name}】" if speaker_name else ""
                                output_txt.write(f"{output_speaker_prefix}{output_dialogue_text}\n")
                                if not config.skip_text:
                                    print()
                                    print(f"原始说话人：{speaker_name}")
                                    print(f"[日文]{dialogue_multi_lang[0][0]}: {dialogue_multi_lang[0][1]}")
                                    if len(dialogue_multi_lang) > 1:
                                        for index, lang in enumerate(("英文", "简中", "繁中"), start=1):
                                            speaker_alias = dialogue_multi_lang[index][0]
                                            dialogue_text = dialogue_multi_lang[index][1]
                                            print(f"[{lang}]{speaker_alias}: {dialogue_text}")
                                    if not config.skip_confirm:
                                        input("按回车键继续：")
                        else:
                            print(f"模式：next")
                        print()

                        nexts_map = {}
                        for next_cached in scene["nexts"]:
                            if next_cached.get("type") == 1:
                                continue
                            signature = utils.generate_next_signature(
                                eval=next_cached.get("eval"),
                                storage=next_cached.get("storage"),
                                target=next_cached.get("target"),
                                type=next_cached.get("type")
                            )
                            nexts_map[signature] = next_cached
                        nexts_eval = []
                        nexts_non_eval = []
                        for next_cached in nexts_map.values():
                            if "eval" in next_cached.keys():
                                nexts_eval.append(next_cached)
                            else:
                                if config.adult_enabled:
                                    x_signature = utils.generate_next_signature(
                                        eval=next_cached.get("eval"),
                                        storage="x_" + next_cached.get("storage"),
                                        target=next_cached.get("target"),
                                        type=next_cached.get("type")
                                    )
                                    if x_signature in nexts_map.keys():
                                        continue
                                elif next_cached["storage"].startswith("x_"):
                                    non_x_signature = utils.generate_next_signature(
                                        eval=next_cached.get("eval"),
                                        storage=next_cached.get("storage").removeprefix("x_"),
                                        target=next_cached.get("target"),
                                        type=next_cached.get("type")
                                    )
                                    if non_x_signature in nexts_map.keys():
                                        continue
                                nexts_non_eval.append(next_cached)
                        assert len(nexts_non_eval) <= 1
                        for next_eval in nexts_eval:
                            print(f"有条件判断eval：{next_eval["eval"]}\t", end="")
                            if ctx.eval(next_eval["eval"]):
                                if next_eval.get("exp"):
                                    ctx.eval(next_eval["exp"])
                                storage = next_eval["storage"]
                                target = next_eval["target"]
                                print("成立√")
                                print(f"\tstorage: {storage}")
                                print(f"\ttarget: {target}")
                                break
                            else:
                                print("不成立×")
                        else:
                            if not nexts_non_eval:
                                print("没有可用的下一场景，线路结束")
                                current_scn = None
                                break
                            if nexts_non_eval[0].get("exp"):
                                ctx.eval(nexts_non_eval[0]["exp"])
                            storage = nexts_non_eval[0]["storage"]
                            if "target" in nexts_non_eval[0].keys():
                                target = nexts_non_eval[0]["target"]
                            else:
                                target = None
                            print("无条件判断：")
                            print(f"\tstorage: {storage}")
                            print(f"\ttarget: {target}")

                    else:
                        raise RuntimeError("?")

                    assert storage is not None
                    print()
                    print("下一个scene已确定：")
                    print(f"\tstorage: {storage}")
                    print(f"\ttarget: {target}")
                    if storage.strip() == "":
                        print(f"storage为空，回退至当前scenes：{current_scn}")
                        storage = current_scn
                    print("————————————————————")
                    if storage != current_scn:
                        print("storage发生变化，准备读取下一个scenes...")
                        current_scn = storage
                        break
                output_txt.write(f"【第{chapter_count}章】结束\n\n\n\n")
        output_txt.seek(0)
        print(f"正在生成pdf：{config.output_pdf_filepath}，耗时可能较长......")
        build_pdf(raw_text=output_txt.read(),
                  language=language_map[config.dialogue_language_id],
                  outfile=config.output_pdf_filepath)
        print("成功生成pdf.")
        output_txt.close()
