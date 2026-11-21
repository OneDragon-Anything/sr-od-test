"""AppRunRecord 月界重置判据:MONTHLY 周期的自然月桶比较(同月不重置/跨月重置)。

dt 构造直接写记录字段(get_current_dt 依赖真实时钟,判据只比较存量 dt 与
现读 dt 的前 6 位);写盘根重定向 tmp_path(测试纪律:项目目录内不写文件)。
"""

from one_dragon.base.operation.application_run_record import (
    AppRunRecord,
    AppRunRecordPeriod,
)


class _MonthlyProbeRecord(AppRunRecord):

    def __init__(self, dt: str):
        AppRunRecord.__init__(
            self, 'monthly_probe',
            record_period=AppRunRecordPeriod.MONTHLY)
        self.dt = dt


def test_monthly_reset_same_month_keeps(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        'one_dragon.utils.os_utils.get_path_under_work_dir',
        lambda *parts: str(tmp_path),
    )
    record = _MonthlyProbeRecord(dt='20261114')
    monkeypatch.setattr(
        record, 'get_current_dt', lambda: '20261130')
    assert record._should_reset_by_dt() is False, '同自然月不重置'


def test_monthly_reset_cross_month_resets(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        'one_dragon.utils.os_utils.get_path_under_work_dir',
        lambda *parts: str(tmp_path),
    )
    record = _MonthlyProbeRecord(dt='20261114')
    monkeypatch.setattr(
        record, 'get_current_dt', lambda: '20261201')
    assert record._should_reset_by_dt() is True, '跨自然月重置(12-01 月界)'
