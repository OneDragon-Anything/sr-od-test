"""MonthlyEmbersExchangeApp 可测逻辑:兑换顺序 / 结果分支 / 配置 / 运行记录。

运行记录与配置测试把写盘根重定向 tmp_path(monkeypatch os_utils,测试
纪律:项目目录内不写任何文件)。
"""

from one_dragon.base.operation.application_run_record import AppRunRecord
from sr_od.application.monthly_embers_exchange.monthly_embers_exchange_app import (
    classify_purchase_result,
    resolve_exchange_order,
)
from sr_od.application.monthly_embers_exchange.monthly_embers_exchange_config import (
    MonthlyEmbersExchangeConfig,
)
from sr_od.application.monthly_embers_exchange.monthly_embers_exchange_run_record import (
    MonthlyEmbersExchangeRunRecord,
)


def test_resolve_exchange_order_filter_and_dedupe() -> None:
    """开关过滤 + 去重 + 未知项视作关闭;顺序即清单顺序。"""
    order = resolve_exchange_order(
        ['tracks_of_destiny', 'special_pass', 'pass', 'special_pass',
         'junk'],
        {'special_pass': True, 'pass': False,
         'tracks_of_destiny': True},
    )
    assert order == ['tracks_of_destiny', 'special_pass'], order


def test_resolve_exchange_order_all_disabled() -> None:
    """全部关闭 = 空顺序(预期内无事可做,照常标完成)。"""
    assert resolve_exchange_order(
        ['special_pass', 'pass', 'tracks_of_destiny'],
        {'special_pass': False, 'pass': False, 'tracks_of_destiny': False},
    ) == []


def test_classify_purchase_result_branches() -> None:
    """§3.1 分支表:四语义态 + 成功 + 无语义非预期。"""
    assert classify_purchase_result(True, None) == 'BOUGHT'
    assert classify_purchase_result(False, 'SOLD_OUT') == 'SKIP'
    assert classify_purchase_result(False, 'CARD_UNAVAILABLE') == 'SKIP'
    assert classify_purchase_result(False, 'NOT_FOUND') == 'SKIP'
    assert classify_purchase_result(False, 'INSUFFICIENT_MATERIALS') == 'STOP_BALANCE'
    assert classify_purchase_result(False, None) == 'ABORT'


def test_config_defaults_in_memory_and_type_coercion(
    tmp_path,
    monkeypatch,
) -> None:
    """默认值进内存 data(MCP get 不读 null);MCP set 的字符串写入被读取口归一。"""
    monkeypatch.setattr(
        'one_dragon.utils.os_utils.get_path_under_work_dir',
        lambda *parts: str(tmp_path),
    )
    config = MonthlyEmbersExchangeConfig(1, 'one_dragon')
    assert config.data['special_pass_enabled'] is True
    assert config.data['exchange_order'] == [
        'special_pass', 'pass', 'tracks_of_destiny',
    ], '构造时顺序默认值应补进内存 data(canonical 序)'

    # 模拟 MCP set 的字符串落盘(set 工具 value 原样透传)
    config.data['pass_enabled'] = 'false'
    assert config.pass_enabled is False, '字符串开关应归一为 bool'


def test_config_exchange_order_self_heal(
    tmp_path,
    monkeypatch,
) -> None:
    """顺序清单自愈:缺失按 canonical 序补尾、未知剔除、重复去重。"""
    monkeypatch.setattr(
        'one_dragon.utils.os_utils.get_path_under_work_dir',
        lambda *parts: str(tmp_path),
    )
    config = MonthlyEmbersExchangeConfig(1, 'one_dragon')
    config.data['exchange_order'] = ['pass', 'junk', 'pass']
    assert config.exchange_order == [
        'pass', 'special_pass', 'tracks_of_destiny',
    ], '缺失补尾 + 未知剔除 + 去重'


def test_run_record_skip_and_reset(
    tmp_path,
    monkeypatch,
) -> None:
    """skip_note 追加格式(goods:STATUS 分号连接)+ reset 清零。"""
    monkeypatch.setattr(
        'one_dragon.utils.os_utils.get_path_under_work_dir',
        lambda *parts: str(tmp_path),
    )
    record = MonthlyEmbersExchangeRunRecord()
    record.record_purchase('pass', 2)
    record.record_skip('special_pass:SOLD_OUT')
    record.record_skip('tracks_of_destiny:SKIP_BALANCE')
    record.record_balance_left(41382)
    assert record.bought_pass == 2
    assert record.skip_note == 'special_pass:SOLD_OUT;tracks_of_destiny:SKIP_BALANCE'
    assert record.balance_left == 41382

    record.reset_record()
    assert record.run_status == AppRunRecord.STATUS_WAIT
    assert record.bought_pass == 0
    assert record.skip_note == ''
    assert record.balance_left is None
