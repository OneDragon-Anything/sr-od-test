"""cw_game_ports 端口协议契约锁 + 零生产消费守卫(T-120 sim 重设计 批 0)。

出处 = T-120 方案 v2(``.debug/temp/currency_war/t120_sim_redesign/方案.md``,
**易失产物**)§6.2 批 0 行「端口协议定稿并落地…零消费点、不被生产 import」
+ §3.2 端口协议形状 + §3.3 装配纪律;ADR 落点待 T-120 退役批分配,
后续批回填编号(测试纪律「批报告类出处」同判)。

锁面三件:
① 安装槽语义 —— 缺省 None = 生产真实读屏(生产全程不安装,行为逐位
   不变);进程内单装配;卸载复位 None 且幂等;
② 协议 conform —— 假实现(FakeCwObserver/FakeActionSink)结构化满足
   两个 runtime_checkable Protocol(批 1 生产实现落地时同锁辖它);
③ 零生产消费守卫 —— src/sr_od 全树唯一引用 cw_game_ports 的文件 = 协议
   文件自身。这是本批「生产零行为改动」的机器可判形:任何生产文件提前
   消费端口 = 红。合法源码扫描(测试纪律 8②依赖方向/单一源守卫);
   盲区自检 = tmp_path 合成树上验证扫描器能抓新建违规文件(测试纪律 20
   「新文件落错位置时守卫必须能起诉,禁假绿」)。
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
_PORT_FILE = (_SRC_ROOT / 'application' / 'currency_war'
              / 'cw_game_ports.py')

#: 扫描目标子串 = 模块名本体(import 语句/字符串引用/文档提及一律算
#: 消费嫌疑——「零消费点」的宽松口径,人工分类由命中集合的封闭性承担:
#: 唯一合法命中 = 协议文件自身)。
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
    """协议 conform 锁(runtime_checkable 结构化满足)。"""

    def test_fake_observer_satisfies_observation_source(self) -> None:
        assert isinstance(FakeCwObserver(FakeMatch(seed=6)),
                          CwObservationSource)

    def test_fake_sink_satisfies_action_sink(self) -> None:
        assert isinstance(FakeActionSink(FakeMatch(seed=6)), CwActionSink)


class TestZeroProductionConsumption:
    """零生产消费守卫(本批「生产零行为改动」的机器可判形)。"""

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

    def test_only_protocol_file_references_itself(self) -> None:
        """src/sr_od 全树唯一命中 = 协议文件自身。

        红 = 有生产文件提前消费端口(方案 §6.2 批 0「零消费点、不被生产
        import」失守)。批 1 观察改道落地时本锁**按计划同批改写**:
        命中集 = 协议文件 + 改道调用点封闭集(方案 §3.3 守卫锁①的
        「改道集封闭」半边)——跟绿须携批 1 方案指针,不是机械放行。"""
        hits = _scan_port_references(_SRC_ROOT)
        assert hits == [_PORT_FILE], (
            f'生产树出现 {_PORT_NEEDLE} 消费点(零消费判据失守): {hits}')
