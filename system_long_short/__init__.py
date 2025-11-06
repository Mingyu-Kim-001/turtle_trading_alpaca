"""
Turtle Trading System with Long and Short Positions

This package implements a real-time Turtle Trading strategy with support for
both long and short positions.
"""

from .utils import DailyLogger, SlackNotifier, StateManager
from .core import (
  DataProvider,
  IndicatorCalculator,
  SignalGenerator,
  PositionManager,
  OrderManager
)

__all__ = [
  'DailyLogger',
  'SlackNotifier',
  'StateManager',
  'DataProvider',
  'IndicatorCalculator',
  'SignalGenerator',
  'PositionManager',
  'OrderManager'
]
