"""Notification utilities for Slack and Telegram"""

import requests
import re


class SlackNotifier:
  """Send notifications to Slack"""

  def __init__(self, token, channel):
    self.token = token
    self.channel = channel
    self.url = "https://slack.com/api/chat.postMessage"

  def send_message(self, message, title=None):
    """Send a message to Slack"""
    try:
      if title:
        formatted_message = f"*{title}*\n{message}"
      else:
        formatted_message = message

      payload = {
        "channel": self.channel,
        "text": formatted_message,
        "mrkdwn": True
      }

      headers = {
        "Authorization": f"Bearer {self.token}",
        "Content-Type": "application/json"
      }

      response = requests.post(self.url, json=payload, headers=headers)
      response.raise_for_status()
      return True
    except Exception as e:
      print(f"Failed to send Slack message: {e}")
      return False

  def send_summary(self, title, data):
    """Send a formatted summary to Slack"""
    message_lines = []
    for key, value in data.items():
      message_lines.append(f"• {key}: {value}")

    message = "\n".join(message_lines)
    self.send_message(message, title=title)


class TelegramNotifier:
  """Send notifications to Telegram"""

  def __init__(self, bot_token, chat_id):
    self.bot_token = bot_token
    self.chat_id = chat_id
    self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

  def _escape_markdown(self, text):
    """
    Escape special characters for Telegram MarkdownV2
    Telegram requires escaping: _ * [ ] ( ) ~ ` > # + - = | { } . !
    But we want to preserve intentional markdown formatting like *bold*
    """
    # Convert to string if not already
    text = str(text)

    # Don't escape characters inside code blocks (backticks)
    # Simple approach: escape everything except intentional markdown
    # For simplicity, we'll use HTML mode instead of MarkdownV2
    return text

  def send_message(self, message, title=None):
    """Send a message to Telegram"""
    try:
      if title:
        # Use HTML formatting for Telegram (simpler than MarkdownV2)
        formatted_message = f"<b>{title}</b>\n{message}"
      else:
        formatted_message = message

      payload = {
        "chat_id": self.chat_id,
        "text": formatted_message,
        "parse_mode": "HTML"
      }

      response = requests.post(self.url, json=payload)
      response.raise_for_status()

      result = response.json()
      if not result.get('ok'):
        print(f"Telegram API error: {result.get('description')}")
        return False

      return True
    except Exception as e:
      print(f"Failed to send Telegram message: {e}")
      return False

  def send_summary(self, title, data):
    """Send a formatted summary to Telegram"""
    message_lines = []
    for key, value in data.items():
      message_lines.append(f"• {key}: {value}")

    message = "\n".join(message_lines)
    self.send_message(message, title=title)


class MultiNotifier:
  """
  Send notifications to multiple platforms (Slack, Telegram, etc.)
  Useful during transition periods or for redundancy
  """

  def __init__(self, notifiers=None):
    """
    Initialize with a list of notifier instances

    Args:
      notifiers: List of notifier objects (SlackNotifier, TelegramNotifier, etc.)
                Each must have send_message() and send_summary() methods
    """
    self.notifiers = notifiers or []

  def add_notifier(self, notifier):
    """Add a notifier to the list"""
    self.notifiers.append(notifier)

  def send_message(self, message, title=None):
    """Send a message to all configured notifiers"""
    results = []
    for notifier in self.notifiers:
      try:
        result = notifier.send_message(message, title=title)
        results.append(result)
      except Exception as e:
        print(f"Error sending to {notifier.__class__.__name__}: {e}")
        results.append(False)

    # Return True if at least one succeeded
    return any(results) if results else False

  def send_summary(self, title, data):
    """Send a formatted summary to all configured notifiers"""
    for notifier in self.notifiers:
      try:
        notifier.send_summary(title, data)
      except Exception as e:
        print(f"Error sending summary to {notifier.__class__.__name__}: {e}")
