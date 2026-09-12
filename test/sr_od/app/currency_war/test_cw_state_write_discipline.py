"""统一 state 写入纪律锁(D1 旁路/效果域直摸)+ 恢复局旗标 live 接线(D2)。

- **D1(设计 v3.1/v3.2 §3.2.4 硬约束 1,M1 门项)**:①BoardState Field 字段
  禁绕 API 直写(grep 子串守卫锁——容器外零属性赋值;帧替换语义的结构前提);
  ②效果域写纪律 = inventory 方法域(禁直摸 ``.entries`` 内部结构,效果变更
  只经 register_strategy/bump_key/consume_use/advance_node 等方法)。
  手法先例 = ADR-0571 grep 守卫(test_cw_hp_assembly §⑩)+ 锚机制写向隔离
  (test_cw_anchor_registry §12.4-B④):扫描根 + 哨兵 + 变异自检。
- **D2(R1 缺口承接,R3 判定方案规则六)**:恢复局旗标 live 接线——cw_loop
  恢复检测两确认点写 session 执行态 ``cw_resumed_match``,观察汇聚漏斗读旗标
  经 ``observe_screen_context(resumed=...)`` 进派生规则:恢复局弹窗腿在 hist
  空时禁用不猜(防把恢复局首弹窗误推断成开局节点 1),消化后备战帧腿 A 接管。
- **G4(v3.2 对齐)**:效果桥 EffectLedgerBridge 登记类属在册(登记面封闭集,
  桥写点显式签名化时的前置)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_state_journal import (
    install_state_telemetry,
    reset_state_telemetry,
)
from sr_od.application.currency_war.telemetry import state as tel_state


@pytest.fixture()
def journal(tmp_path):
    """装一份指到 tmp 的状态流水(影子面武装;teardown 复位模块全局)。"""
    j = install_state_telemetry(tmp_path / 'state' / 'journal.jsonl',
                                run_id_provider=tel_state.current_run_id)
    yield j
    reset_state_telemetry()


@pytest.fixture()
def run_id(monkeypatch):
    """桩一个 run 归属(行内 run_id 键;teardown 由 monkeypatch 自动还原)。"""
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 'run_test_discipline')
    return 'run_test_discipline'


# ============================================================ 扫描根与判据

_SRC_CW = (Path(__file__).parents[5] / 'src' / 'sr_od' / 'application'
           / 'currency_war')
_BOARD_STATE_MODULE = 'cw_game_state.py'
_EFFECT_INVENTORY_MODULE = 'cw_effect_inventory.py'

#: D1-① 旁路锁扫描根豁免:容器本体(kernel)——Field 属性赋值的唯一合法面
#: (工程结构 write_seq/frame_obs/node_hist_ord/hb_* 与 _swap 内部件)。
_BYPASS_EXEMPT = {_BOARD_STATE_MODULE}

#: D1-① 接收者词表:全仓 GameState 实例的既定接收者命名(bs 绝对主导,
#: kernel/obs/prep/cw_op/sim 一致;新接收者名先登记本表再使用——扩面纪律
#: 同 ADR-0571 grep 守卫)。边界申报:换名接收者的赋值本锁不可见,接收者
#: 命名纪律 = 本锁的登记面前提。
_BYPASS_RECEIVERS = ('bs', 'board_state')


def _bypass_guard_hits(text: str) -> list[str]:
    """D1-① 判据单一实现(主扫描与变异自检共用,防自检复刻判据):
    对 bs/board_state 接收者的**任何**属性赋值(= 形;Field 帧替换只能
    经 API,容器外零合法属性赋值——工程结构也只在容器本体方法内变)。"""
    import re

    recv = '|'.join(_BYPASS_RECEIVERS)
    pat = re.compile(rf'\b(?:{recv})\s*\.\s*[a-z_][a-z_0-9]*\s*=(?!=)')
    return [m.group(0) for m in pat.finditer(text)]


#: D1-② 效果域内部结构变异判据(经 effects/effect_inventory 接收者链直达
#: .entries 的变异形态;读面(迭代/取值)不在禁令内——禁的是写)。
_EFFECT_MUTATOR = (r'\.append|\.extend|\.insert|\.remove|\.pop|\.clear'
                   r'|\.sort|\.reverse|\[[^\]]*\]\s*=|\s*=[^=]')


def _effects_guard_hits(text: str) -> list[str]:
    """D1-② 判据单一实现(主扫描与变异自检共用)。"""
    import re

    pat = re.compile(
        rf'(?:effects|effect_inventory)\.entries(?:{_EFFECT_MUTATOR})')
    return [m.group(0) for m in pat.finditer(text)]


def _scan_src(exempt: set[str], guard) -> dict[str, str]:
    """扫描根遍历(哨兵 + 文件数下限防根失准假绿;豁免面显式申报)。"""
    sentinel = _SRC_CW / 'kernel' / _BOARD_STATE_MODULE
    assert sentinel.is_file(), f'扫描根解析失准:{_SRC_CW}'
    scanned = list(_SRC_CW.rglob('*.py'))
    assert len(scanned) >= 60, f'扫描文件数异常({len(scanned)}),根可能错位'
    offenders: dict[str, str] = {}
    for path in scanned:
        if path.name in exempt:
            continue
        rel = path.relative_to(_SRC_CW).as_posix()
        for hit in guard(path.read_text(encoding='utf-8')):
            offenders[f'{rel}:{hit}'] = hit
    return offenders


# ============================================================ D1-① Field 旁路 grep 锁(§3.2.4 硬约束 1)


def test_board_state_field_bypass_grep_lock() -> None:
    """旁路直改锁(§3.2.4 硬约束 1①):容器外(kernel/cw_game_state.py 之外
    全子树)零「bs/board_state.<attr> =」形态——Field 帧替换只经 observe/
    carry/write_prior/write_logic/relay API(两态制 ADR-0651:expect/confirm
    已废除,write_logic = 标准逻辑写通道);工程结构
    (write_seq/node_hist_ord 等)只在容器本体方法内变。变异自检防判据失准。"""
    assert _bypass_guard_hits('bs.gold = Field(value=1)') == ['bs.gold ='], \
        '变异自检未命中'
    assert _bypass_guard_hits('bs.gold == 1') == [], '等比比较误报(== 形)'
    assert _bypass_guard_hits('state.gold = 1') == [], \
        'CwWorkFrame 接收者不在禁令内(旧容器直改归其自身纪律)'
    offenders = _scan_src(_BYPASS_EXEMPT, _bypass_guard_hits)
    assert not offenders, (
        'GameState 属性被容器外直改(禁令 = §3.2.4 硬约束 1:op 层一律经 '
        f'API 写,全仓硬约束):{offenders}')


# ============================================================ D1-② 效果域直摸 grep 锁(§3.2.4 硬约束 1)


def test_effects_internal_mutation_grep_lock() -> None:
    """效果域直摸锁(§3.2.4 硬约束 1②):``.entries`` 内部结构变异只允许
    发生在 inventory 方法域本体(cw_effect_inventory.py);其余全子树
    (含 cw_game_state 桥/快照——只读)禁直达 entries 变异。合法读面
    (3 处迭代)不在禁令。变异自检防判据失准。"""
    assert _effects_guard_hits(
        'bs.effects.entries.append(x)') == ['effects.entries.append'], \
        '变异自检未命中'
    assert _effects_guard_hits(
        'for e in bs.effects.entries:\n    pass') == [], '合法读面误报'
    offenders = _scan_src({_EFFECT_INVENTORY_MODULE}, _effects_guard_hits)
    assert not offenders, (
        '效果账本内部结构被 inventory 方法域外直摸(禁令 = §3.2.4 硬约束 1:'
        f'效果域写纪律 = inventory 方法域):{offenders}')


# ============================================================ G4 对齐(v3.2:效果桥登记类属)


def test_v32_effect_bridge_actor_registered() -> None:
    """v3.2-G4:EffectLedgerBridge 登记类属在册(§3.2.1 登记面;桥写点
    显式签名化时的前置——project_effect_capacity/grant_effect_node_
    refresh_balance 的在册身份)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        actor_registered,
    )
    assert actor_registered('EffectLedgerBridge'), \
        '效果桥未登记(v3.2-G4 §3.2.1 登记类属补项)'


# ============================================================ D2 恢复局旗标 live 接线(R3 规则六)


def _resumed_probe_ctx(session) -> SimpleNamespace:
    # screen_loader 恒 None:商店开态喂入口经按钮态 composite 读链
    # (read_shop_refresh_button,见 cw_shop_refresh_obs 模块头)需经
    # ctx.screen_loader 取「标识-免费刷新」/「文本-刷新价格」建档;
    # None = 建档缺失失读形态(reader 产出 free=None → 漏斗 carry 回退),
    # 与下方刷新费识别桩同守「识别失败=None 禁兜底」语义,不触真 OCR。
    return SimpleNamespace(cw_match=SimpleNamespace(session=session),
                           screen_loader=SimpleNamespace(
                               get_screen=lambda name: None))


def test_resumed_flag_live_disables_popup_leg(journal, run_id, monkeypatch):
    """D2 主锁(全走生产漏斗):恢复局旗标(执行态)经漏斗进派生——恢复局
    首弹窗在 hist 空时禁用不猜(R3 规则六),防误推断开局节点 1;旗标 False
    的对照臂同序列正常推断候选 1(正常新局开局推断合法,不误伤)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        board_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_exec_state import (
        exec_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import CwWorkFrame
    from sr_od.application.currency_war.obs import cw_shop_refresh_obs
    from sr_od.application.currency_war.obs.cw_observation import (
        PHASE_BATTLE_OR_TRANSIT,
        PHASE_PREP_SHOP_OPEN,
        _feed_board_state,
    )

    def _probe(*, resumed: bool):
        # 刷新费识别桩(店开帧通道,识别失败=None 禁兜底——与生产失读帧同形)
        monkeypatch.setattr(cw_shop_refresh_obs, 'read_shop_refresh_price',
                            lambda ctx, screen: None)
        session = SimpleNamespace()
        if resumed:
            exec_state_of(session).cw_resumed_match = True   # 生产写端 = cw_loop 两确认点
        ctx = _resumed_probe_ctx(session)
        # 帧 1:战斗/过渡相位(恢复局重入首帧形态)→ 漏斗写分支 token
        state = CwWorkFrame()
        state.plane, state.round_num = 2, 3
        _feed_board_state(ctx, state, PHASE_BATTLE_OR_TRANSIT, None,
                          frozenset(), had_hp_real=False)
        # 帧 2:商店面板先被采到(恢复局首弹窗形态)→ 弹窗腿判定
        state2 = CwWorkFrame()
        state2.plane, state2.round_num = 2, 3
        _feed_board_state(ctx, state2, PHASE_PREP_SHOP_OPEN, None,
                          frozenset(), had_hp_real=False)
        bs = board_state_of(session)
        assert bs.current_screen.value == '货币战争-备战-开商店', \
            '漏斗弹窗帧写入(前置)'
        return bs.node_ord.value

    assert _probe(resumed=True) is None, \
        '恢复局弹窗腿禁用不猜(旗标 live 进派生,R3 规则六)'
    assert _probe(resumed=False) == 1, \
        '正常新局同序列开局推断合法(旗标缺省 False 不误伤)'


def test_resumed_flag_writer_anchors_in_cw_loop() -> None:
    """D2 源面锁:cw_loop 恢复检测两确认点(战斗帧检测/备战帧 resume_
    candidate 确认)都接 _mark_session_resumed 写端(防单腿断链)。"""
    import inspect

    from sr_od.application.currency_war.operations.cw_loop import CwLoop

    src = inspect.getsource(CwLoop)
    assert src.count('self._mark_session_resumed()') >= 2, \
        '恢复局旗标写端两确认点齐(D2:战斗帧检测 + 备战帧确认)'
    assert '_mark_session_resumed' in src, '写端方法缺失'


def test_resumed_flag_funnel_passthrough_anchor() -> None:
    """D2 漏斗面锚:观察汇聚漏斗把执行态旗标透传进 observe_screen_context
    (resumed= 形参在位,防接线回退到 R1 缺省 False 形态)。"""
    import inspect

    import sr_od.application.currency_war.obs.cw_observation as obs_mod

    src = inspect.getsource(obs_mod)
    assert 'resumed=' in src, '漏斗未透传恢复局旗标(D2 接线回退)'
