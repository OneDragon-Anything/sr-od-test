"""cw_game_ports 端口协议契约锁 + 改道集封闭守卫(T-120 sim 重设计
批 0 落地,批 1 按预写跟绿条件改写消费面锁)。

出处 = T-120 方案 v2(``.debug/temp/currency_war/t120_sim_redesign/方案.md``,
**易失产物**)§6.2 批 0 行(批 0「零消费点」)+ §3.3 装配纪律与守卫锁①
(批 1 起消费面 = 改道调用点封闭集)+ §6.2 批 1 行;ADR 落点待 T-120
退役批分配,后续批回填编号(测试纪律「批报告类出处」同判)。

锁面三件:
① 安装槽语义 —— 缺省 None = 生产真实读屏(生产全程不安装,行为逐位
   不变);进程内单装配;卸载复位 None 且幂等;
② 协议 conform —— 假实现(FakeCwObserver/FakeActionSink)结构化满足
   两个 runtime_checkable Protocol + 签名级形状锁(批 0 落地审 L4 修后
   口径,isinstance 的方法名盲区由 inspect.signature 补);
③ 改道集封闭守卫 —— 生产树消费 cw_game_ports 的文件 = 协议 + 批 1
   改道调用点封闭集(合法源码扫描,测试纪律 8②依赖方向/单一源守卫;
   盲区自检 = tmp_path 合成树验证扫描器能起诉,测试纪律 20)。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fixtures.cw_fake_game.fake_match import FakeMatch
from fixtures.cw_fake_game.fake_ports import FakeActionSink, FakeCwObserver

from sr_od.application.currency_war.cw_game_ports import (
    CwActionSink,
    CwObservationSource,
    action_sink,
    install_game_ports,
    observation_source,
    uninstall_game_ports,
)

_REPO_ROOT = Path(__file__).resolve().parents[5]   # 仓库根(currency_war 测试 ← app ← sr_od ← test ← sr-od-test ← 根)
_SRC_ROOT = _REPO_ROOT / 'src' / 'sr_od'

#: 扫描目标子串 = 模块名本体(import 语句/字符串引用/文档提及一律算
#: 消费嫌疑——宽松口径,分类由命中集合与封闭集的比对承担)。
_PORT_NEEDLE: str = 'cw_game_ports'


@pytest.fixture(autouse=True)
def _ports_isolated():
    """模块槽是进程全局态——teardown 强制卸载(测试纪律 4:隔离整条
    副作用链,不依赖「我调了什么」;残留会跨测试文件泄漏)。"""
    yield
    uninstall_game_ports()


def _scan_port_references(root: Path) -> list[Path]:
    """扫 root 下全部 .py(跳 __pycache__),返回内容含端口模块名的文件
    (路径排序,保证断言确定性)。"""
    hits: list[Path] = []
    for p in sorted(root.rglob('*.py')):
        if '__pycache__' in p.parts:
            continue
        try:
            text = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if _PORT_NEEDLE in text:
            hits.append(p)
    return hits


class TestInstallSlot:
    """安装槽语义锁(方案 §3.2/§3.3:缺省关 + 显式接通 + 卸载复位)。"""

    def test_default_is_none_production_path(self) -> None:
        """缺省 None = 生产路径:生产全程不安装,调用点按 None 分流走
        原读链/原执行链(方案 §3.2「缺省 None = 生产路径」)。"""
        assert observation_source() is None
        assert action_sink() is None

    def test_install_sets_both_uninstall_resets(self) -> None:
        """安装后两端口可达;卸载复位 None(测试隔离纪律的载体)。"""
        match = FakeMatch(seed=1)
        observer = FakeCwObserver(match)
        sink = FakeActionSink(FakeMatch(seed=2))
        install_game_ports(observer, sink)
        assert observation_source() is observer
        assert action_sink() is sink
        uninstall_game_ports()
        assert observation_source() is None
        assert action_sink() is None

    def test_double_install_raises(self) -> None:
        """进程内单装配:重复安装 raise(静默覆盖会让前一套假游戏的断言
        读到后一套的状态,错误形态必须是响的)。"""
        install_game_ports(FakeCwObserver(FakeMatch(seed=3)),
                           FakeActionSink(FakeMatch(seed=3)))
        with pytest.raises(RuntimeError, match='已安装'):
            install_game_ports(FakeCwObserver(FakeMatch(seed=4)),
                               FakeActionSink(FakeMatch(seed=4)))

    def test_install_rejects_none(self) -> None:
        """清槽语义只归 uninstall,install 不接受 None(显式分明,防
        半装配态:只装观察不装执行器之类的静默残缺)。"""
        with pytest.raises(ValueError, match='None'):
            install_game_ports(None,  # type: ignore[arg-type]
                               FakeActionSink(FakeMatch(seed=5)))

    def test_uninstall_idempotent(self) -> None:
        """卸载幂等(未安装态卸载 = no-op;teardown 可无脑调用)。"""
        uninstall_game_ports()
        uninstall_game_ports()
        assert observation_source() is None
        assert action_sink() is None


class TestProtocolConformance:
    """协议 conform 锁(runtime_checkable 结构化满足 + 签名级断言)。

    签名级断言 = 批 0 落地审 L4 修后口径:isinstance 检查只验方法名
    在场,``execute_action`` 漏 ``action``/``env`` 参或参数改名时结构化
    conform 仍绿——批 1 起两端口实现与改道调用点都以签名为承重面
    (env 语境承载账本位随动),用 inspect.signature 形状锁补盲区。
    """

    @staticmethod
    def _param_names(func) -> list[str]:
        import inspect
        return list(inspect.signature(func).parameters)

    def test_fake_observer_satisfies_observation_source(self) -> None:
        assert isinstance(FakeCwObserver(FakeMatch(seed=6)),
                          CwObservationSource)

    def test_fake_sink_satisfies_action_sink(self) -> None:
        assert isinstance(FakeActionSink(FakeMatch(seed=6)), CwActionSink)

    def test_sink_signature_matches_protocol_shape(self) -> None:
        """execute_action 形状锁:协议 (ctx, action, env) 三参;env 缺省
        None = 生产语境可缺省(方案 §3.3 改道点批 1 起 env 恒传,fake
        保留缺省 = 独立可驱动)。"""
        from sr_od.application.currency_war.cw_game_ports import CwActionSink
        proto_params = self._param_names(CwActionSink.execute_action)
        assert proto_params == ['self', 'ctx', 'action', 'env']
        fake_params = self._param_names(FakeActionSink.execute_action)
        assert fake_params == proto_params, (
            f'FakeActionSink.execute_action 签名与协议漂移:'
            f'{fake_params} != {proto_params}')

    def test_observer_methods_signature_match(self) -> None:
        """观察源四方法签名锁(同 L4 口径;observe_prep 的 phase 键、
        overlay_options 的 kind 键是改道调用点的承重参数)。"""
        for name, params in (
                ('screen_identity', ['self', 'ctx']),
                ('observe_prep', ['self', 'ctx', 'phase']),
                ('observe_shop_cards', ['self', 'ctx']),
                ('overlay_options', ['self', 'ctx', 'kind'])):
            proto = getattr(CwObservationSource, name)
            fake = getattr(FakeCwObserver, name)
            assert self._param_names(proto) == params, f'协议漂移:{name}'
            assert self._param_names(fake) == params, (
                f'FakeCwObserver.{name} 签名与协议漂移')


class TestZeroProductionConsumption:
    """改道集封闭守卫(方案 §3.3 守卫锁①的「改道集封闭」半边)。

    批 0 锁「零消费」;批 1 起按批 0 预写的跟绿条件改写:生产树对
    cw_game_ports 的引用面 = 协议文件 + 改道调用点**封闭集**——集合外
    新增消费 = 旁路改道(未登记的读屏/执行新缝),红。当前封闭集
    (批 1 改道清单,方案 §6.2 批 1 行 + §7.1 文件面;批 2 增补
    cw_screen_op_base 一项,理由见集合内注):

    - cw_game_ports.py —— 协议本体(槽与两 Protocol);
    - operations/cw_op/cw_op_buy_cards.py —— 商店入口观察改道 +
      动作执行步改道(§3.3 执行面);
    - operations/cw_screen/cw_screen_prep.py —— 备战入口 heavy 观察
      改道(§2.3 表消费点);
    - operations/cw_screen/cw_screen_op_base.py —— docstring 提及,
      非改道点(试点基类,零 import 零调用);
    - operations/decision_frame_hooks.py —— 留证面改形(§2.3 契约
      三则:假环境落结构化观察 JSON)。
    """

    #: 封闭集(相对 src/sr_od 的路径尾;新改道点必须同批登记本表)
    _CLOSED_SUFFIXES: tuple[str, ...] = (
        str(Path('application') / 'currency_war' / 'cw_game_ports.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_op'
            / 'cw_op_buy_cards.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_prep.py'),
        # 统一观察架构试点步骤 2(逐屏迁移首批,§9.2 迁移步骤 4 + B3 两
        # 代表屏):遭遇/盛会之星 handle 顶部装配点分流判据消费
        # observation_source/action_sink(与 cw_screen_prep.run 同式,
        # §9.1 并存期机制面;非旁路改道——零读屏/执行新缝,两屏缺省
        # None = 生产直连旧路径)。
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_encounter.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_megastar.py'),
        # 统一观察架构试点步骤 3(逐屏迁移第二批量,§9.2 迁移步骤 4 +
        # B3 三段走第二段「补给 + 余事件屏按族批量」):八屏决策承载节点
        # 顶部装配点分流判据消费 observation_source/action_sink(与步骤 2
        # 两屏同式,§9.1 并存期机制面;非旁路改道——零读屏/执行新缝,缺省
        # None = 生产直连旧路径。专家邀请函分流在选卡节点,开卡节点留旧
        # 路径,申报面见其模块 docstring 与迁移锁源面锁)。
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_supply_node.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_partner.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_planner.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_wish_trial.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_fortune.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_bookcard.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_equip_pick.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_expert_invite.py'),
        # 统一观察架构余项收口阶段一(账本 T-8 五相位屏;设计 =
        # changes/2026-09-11-unified-observation/ landing 阶段一 + 五相位屏
        # 迁移详设):投资环境/投资策略/战斗等待/简报/BOSS 简报五屏 start
        # 节点方法顶部装配点分流判据消费 observation_source/action_sink
        #(先例锚 = cw_screen_encounter.py 装配点分流;重入裁决留守分流前
        # 共享段,总纲契约 6。非旁路改道——零读屏/执行新缝,缺省 None =
        # 生产直连旧路径,§9.1 并存期)。
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_invest_env.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_invest_strategy.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_battle_wait.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_briefing.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_boss_briefing.py'),
        # 统一观察架构余项收口阶段二(账本 T-47 推进型基类收编;设计 =
        # changes/2026-09-11-unified-observation/ landing 阶段二 + 推进型
        # 基类收编详设):CwProgressionScreenOp 重挂 CwScreenOpBase 作
        # 只读/导航变体,handle 顶部装配点分流判据消费
        # observation_source/action_sink(先例锚同上;ADR-0584 空决策合同
        # 逐字保留,11 子类零改动。非旁路改道——零读屏/执行新缝,缺省
        # None = 生产直连现役骨架,§9.1 并存期)。
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / '_progression_base.py'),
        # 统一观察架构余项收口阶段三(账本 T-48 收尾五屏;设计 =
        # changes/2026-09-11-unified-observation/ landing 阶段三 + 收尾屏
        # 迁移详设):位面过渡/武装箱弹窗/未达上限弹窗/等待1-1/位面情报采集
        # 五屏 start 节点方法顶部(handle / collect() 节点首行)装配点分流
        # 判据消费 observation_source/action_sink(先例锚同上;重入裁决留守
        # 分流前共享段,总纲契约 6;位面情报采集 = 薄转录,总纲契约 2。
        # 非旁路改道——零读屏/执行新缝,缺省 None = 生产直连旧路径,
        # §9.1 并存期)。
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_plane_transition.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_armory_box.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_deploy_not_full.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_wait_one_one.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_plane_intel.py'),
        # 统一观察架构 B4 挂账批(账本 T-45 商店系三件收编;设计依据 =
        # changes/2026-09-11-unified-observation/design.md §2.1-4 挂账行 +
        # 推进型基类收编详设变体形态):cw_op_open_shop/cw_op_close_shop
        # 改挂 CwScreenOpBase 作只读/导航变体,open/close 节点顶部装配点
        # 分流判据消费 observation_source/action_sink(先例锚同上;幂等
        # 原子动作零策略消费,decide 空申报。非旁路改道——零读屏/执行
        # 新缝,缺省 None = 生产直连旧函数,§9.1 并存期)。cw_op_buy_cards
        # 为既有登记面(商店入口观察改道),本批仅增同式分流判据。
        str(Path('application') / 'currency_war' / 'operations' / 'cw_op'
            / 'cw_op_open_shop.py'),
        str(Path('application') / 'currency_war' / 'operations' / 'cw_op'
            / 'cw_op_close_shop.py'),
        # 统一观察架构试点步骤 1(commit 3a688669a)基类:docstring 提及
        # 安装协议名(「双清复位见 cw_game_ports」),零 import 零调用——
        # 扫描为文本匹配,提及即命中;非改道点,批 2 登记豁免。
        str(Path('application') / 'currency_war' / 'operations' / 'cw_screen'
            / 'cw_screen_op_base.py'),
        str(Path('application') / 'currency_war' / 'operations'
            / 'decision_frame_hooks.py'),
        # 观测锚实现批①(T-221,统一观察架构 §12):kernel/cw_anchor.py
        # 模块 docstring 以「cw_game_ports 消费面封闭集」为登记式先例引名
        # (与 op_base 同形态:扫描为文本匹配,提及即命中)——零 import
        # 零调用(惰性纯机制面,其零生产消费另有守卫锁
        # test_cw_anchor_registry::test_anchor_mechanism_lazy 独立钉死),
        # 非改道点,登记豁免。
        str(Path('application') / 'currency_war' / 'kernel'
            / 'cw_anchor.py'),
    )

    def test_scanner_catches_new_violations(self, tmp_path: Path) -> None:
        """盲区自检:合成树上的新建违规文件必须被起诉(禁假绿)。"""
        pkg = tmp_path / 'pkg'
        pkg.mkdir()
        guilty = pkg / 'offender.py'
        guilty.write_text(
            'from sr_od.application.currency_war import cw_game_ports\n',
            encoding='utf-8')
        (pkg / 'clean.py').write_text('x: int = 1\n', encoding='utf-8')
        hits = _scan_port_references(tmp_path)
        assert hits == [guilty]

    def test_redirect_set_is_closed(self) -> None:
        """生产树命中集 = 封闭集逐一对上(多/少/错位皆红)。

        红 = 集合外生产文件消费端口(旁路改道)——处理 = 审其改道
        合法性:合法 → 同批登记本封闭集并携方案指针;不合法 → 改道
        收敛到已登记点。禁机械跟绿。"""
        hits = _scan_port_references(_SRC_ROOT)
        hit_suffixes = sorted(
            str(h.relative_to(_SRC_ROOT)).replace('\\', '/')
            for h in hits)
        expected = sorted(s.replace('\\', '/') for s in self._CLOSED_SUFFIXES)
        assert hit_suffixes == expected, (
            f'cw_game_ports 生产消费面越出封闭集:\n'
            f'  实际 = {hit_suffixes}\n  封闭集 = {expected}')
