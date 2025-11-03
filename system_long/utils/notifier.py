"""Slack notification utilities"""

import requests


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
