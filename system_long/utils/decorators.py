"""Utility decorators for error handling and retries"""

from functools import wraps
import time
import requests


def retry_on_connection_error(max_retries=3, initial_delay=1, backoff=2):
  """
  Decorator to retry API calls on connection errors

  Args:
    max_retries: Maximum number of retry attempts
    initial_delay: Initial delay between retries in seconds
    backoff: Backoff multiplier for exponential delay
  """
  def decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
      delay = initial_delay
      last_exception = None

      for attempt in range(max_retries):
        try:
          return func(*args, **kwargs)
        except (ConnectionResetError, ConnectionError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout) as e:
          last_exception = e
          if attempt < max_retries - 1:
            print(f"Connection error in {func.__name__} (attempt {attempt + 1}/{max_retries}): {e}")
            print(f"Retrying in {delay} seconds...")
            time.sleep(delay)
            delay *= backoff
          else:
            print(f"Failed after {max_retries} attempts in {func.__name__}")

      # If all retries failed, log but don't crash
      print(f"All retries exhausted for {func.__name__}: {last_exception}")
      return None

    return wrapper
  return decorator
