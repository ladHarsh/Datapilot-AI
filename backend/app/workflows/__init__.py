"""
workflows/__init__.py — SQL AI Analytics Platform.
"""
from .sql_generation_workflow import run as run_sql_workflow    # noqa: F401
from .voice_workflow import run as run_voice_workflow           # noqa: F401
from .analytics_workflow import run as run_analytics_workflow  # noqa: F401
from .chart_workflow import run as run_chart_workflow           # noqa: F401
