"""The send pipeline: the hourly run, the preview, and the due-date rules behind them.

Called over HTTP from :mod:`wishly.api.routes.internal`, not by a scheduler of
its own — see :mod:`wishly.orchestration.runner`.
"""
