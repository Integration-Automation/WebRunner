"""
Core Web Vitals 預算斷言 / One budget assertion for LCP, CLS, INP and FCP (``WR_assert_web_vitals``).
"""
from je_web_runner.utils.web_vitals.vitals import (
    GOOD,
    POOR,
    WebVitalsError,
    assert_web_vitals,
    evaluate,
    lighthouse_measurement,
    measure_page,
    rate,
    write_reports,
)

__all__ = [
    "GOOD", "POOR", "WebVitalsError", "assert_web_vitals", "evaluate", "lighthouse_measurement",
    "measure_page", "rate", "write_reports",
]
