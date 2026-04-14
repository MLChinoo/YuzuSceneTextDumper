from pydantic import Field

from configs import BaseConfig


class DracuConfig(BaseConfig):
    # 不建议更改
    head_scn: str = Field("★プロローグa（始まり）.ks", description="初始场景scn名称")
    head_label: str = Field("*prologue_A", description="初始场景标签")

    # 建议启用，若禁用则下面四个选项也自动禁用，不论设置
    adult_enabled: bool = Field(True, description="是否启用R18内容（总开关）")

    is_trial: bool = Field(False, description="是否为体验版")

    clear_miu: bool = Field(True, description="是否已通关美羽路线")

    clear_azu: bool = Field(True, description="是否已通关梓路线")

    clear_rio: bool = Field(True, description="是否已通关莉音路线")

    clear_eri: bool = Field(True, description="是否已通关艾莉娜路线")

    clear_nic: bool = Field(True, description="是否已通关尼古拉路线")

    check_in: bool = Field(True, description="H场景选项：中出")

    check_out: bool = Field(True, description="H场景选项：外射")

    check_mouth: bool = Field(True, description="H场景选项：口射")

    check_face: bool = Field(True, description="H场景选项：颜射")

    def _check_valid(self):
        # 若启用R18内容，则 中出/外射（口射/颜射）不可以同时禁用，否则无法选择选项，推进流程时卡死
        if self.adult_enabled:
            assert self.check_in or self.check_out
            assert self.check_mouth or self.check_face