from enum import IntEnum

from pydantic import Field

from configs import BaseConfig


class DracuConfig(BaseConfig):        
    # 不建议更改
    head_scn: str = Field("★プロローグa（始まり）.ks", description="初始场景scn名称")
    head_label: str = Field("*prologue_A", description="初始场景标签")

    is_trial: bool = Field(False, description="是否为体验版")

    clear_miu: bool = Field(True, description="是否已通关美羽路线")

    clear_azu: bool = Field(True, description="是否已通关梓路线")

    clear_rio: bool = Field(True, description="是否已通关莉音路线")

    clear_eri: bool = Field(True, description="是否已通关艾莉娜路线")

    clear_nic: bool = Field(True, description="是否已通关尼古拉路线")

    # 建议启用，若禁用则下面四个选项也自动禁用，不论设置
    adult_enabled: bool = Field(True, description="是否启用R18内容（总开关）")

    check_in: bool = Field(True, description="H场景选项：中出")

    check_out: bool = Field(True, description="H场景选项：外射")

    check_mouth: bool = Field(True, description="H场景选项：口射")

    check_face: bool = Field(True, description="H场景选项：颜射")

    # 场景文件中某些对话文本同时存在“正文文本”与“注音文本”两个变体，
    # “注音文本”会将“正文文本”中易混淆读音的汉字替换为假名表示，方便语音合成引擎等用途，如：
    #     dialogue[1]（原文本）： 「ふぅ……次の[クラ]患[ンケ]者は？」
    #     dialogue[3]（注音文本）： 「ふぅ……次のクランケは？」
    #     dialogue[4]（正文文本）： 「ふぅ……次の患者は？」
    # 注意：若某对话文本不存在这两种变体，则仍回退到“原文本”。
    class DialogueTextVariant(IntEnum):
        ORIGINAL_TEXT = 1  # 原文本
        PHONETIC_TEXT = 3  # 注音文本
        WRITTEN_TEXT = 4  # 正文文本
    dialogue_text_variant: DialogueTextVariant = Field(
        DialogueTextVariant.WRITTEN_TEXT,
        description="文本变体偏好",
    )

    dick_word_table: dict[str, dict[str, list[str]]] = Field(
        default_factory=lambda: {
            "jp": {
                "word": ["おち●ちん", "おち●ぽ", "ち●ぽ"],
                "wordx": ["お、", "お、", "ち、"],
            },
            "en": {
                "word": ["penis", "dick", "cock"],
                "wordx": ["p...", "d...", "c..."],
            },
            "cn": {
                "word": ["小鸡鸡", "鸡巴", "肉棒"],
                "wordx": ["小、", "鸡、", "肉、"],
            },
            "tw": {
                "word": ["小雞雞", "雞巴", "肉棒"],
                "wordx": ["小、", "雞、", "肉、"],
            },
        },
        description="提取美羽线所依赖的用词表，三项依次对应三个选择。数据来自adult/dick_words.txt",
    )

    def _check_valid(self):
        # 若启用R18内容，则 中出/外射（口射/颜射）不可以同时禁用，否则无法选择选项，推进流程时卡死
        if self.adult_enabled:
            assert self.check_in or self.check_out
            assert self.check_mouth or self.check_face
