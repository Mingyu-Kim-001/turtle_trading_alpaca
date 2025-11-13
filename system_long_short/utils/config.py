"""Configuration loader for Turtle Trading System"""

import os
import re
from typing import Optional
from pathlib import Path


def expand_env_vars(value: str, env_vars: dict) -> str:
    """
    Expand environment variable references in a string.
    
    Supports:
    - ${VAR} or ${VAR:-default} syntax
    - $VAR syntax (simple, no default)
    
    Args:
        value: String that may contain variable references
        env_vars: Dictionary of already loaded env vars (for .env file variables)
    
    Returns:
        String with variables expanded
    """
    def replace_var(match):
        var_expr = match.group(1)  # Content inside ${} or after $
        
        # Handle ${VAR:-default} syntax
        if ':-' in var_expr:
            var_name, default_value = var_expr.split(':-', 1)
            var_name = var_name.strip()
            default_value = default_value.strip()
        else:
            var_name = var_expr.strip()
            default_value = None
        
        # Check in order: env_vars (from .env), os.environ, then default
        if var_name in env_vars:
            return env_vars[var_name]
        elif var_name in os.environ:
            return os.environ[var_name]
        elif default_value is not None:
            return default_value
        else:
            # Variable not found and no default - return original (or empty?)
            return match.group(0)  # Return original if not found
    
    # Replace ${VAR} or ${VAR:-default} patterns
    value = re.sub(r'\$\{([^}]+)\}', replace_var, value)
    
    # Replace $VAR patterns (simple, no braces)
    # Only replace if it's a valid variable name (alphanumeric + underscore)
    value = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', replace_var, value)
    
    return value


def str_to_bool(value: str) -> bool:
    """Convert string to boolean"""
    if isinstance(value, bool):
        return value
    if value.lower() in ('true', '1', 'yes', 'on'):
        return True
    elif value.lower() in ('false', '0', 'no', 'off'):
        return False
    else:
        raise ValueError(f"Cannot convert '{value}' to boolean")


def load_env_file(env_file: str = '.env') -> dict:
    """
    Load environment variables from .env file

    Args:
        env_file: Path to .env file (default: '.env' in project root)

    Returns:
        Dictionary of environment variables
    """
    # Find project root (where .env should be)
    current_dir = Path(__file__).parent
    project_root = current_dir.parent.parent
    env_path = project_root / env_file

    if not env_path.exists():
        print(f"Warning: {env_path} not found. Using system environment variables only.")
        return {}

    env_vars = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                env_vars[key] = value

    # Expand environment variables in values (supports references to OS env vars)
    # We do this in a loop to handle variables that reference other variables
    max_iterations = 10  # Prevent infinite loops
    for _ in range(max_iterations):
        changed = False
        for key, value in env_vars.items():
            expanded = expand_env_vars(value, env_vars)
            if expanded != value:
                env_vars[key] = expanded
                changed = True
        if not changed:
            break

    return env_vars


class TradingConfig:
    """Configuration for live trading system"""

    def __init__(self, env_file: str = '.env'):
        """
        Load configuration from .env file

        Args:
            env_file: Path to .env file (default: '.env')
        """
        # Load .env file
        env_vars = load_env_file(env_file)

        # Update os.environ with .env values (but don't override existing env vars)
        for key, value in env_vars.items():
            if key not in os.environ:
                os.environ[key] = value

        # API Credentials
        self.alpaca_key = os.environ.get('ALPACA_API_KEY')
        self.alpaca_secret = os.environ.get('ALPACA_SECRET')
        self.slack_token = os.environ.get('SLACK_BOT_TOKEN')
        self.slack_channel = os.environ.get('PERSONAL_SLACK_CHANNEL_ID')

        # Validate required credentials
        if not all([self.alpaca_key, self.alpaca_secret, self.slack_token, self.slack_channel]):
            raise ValueError(
                "Missing required credentials. Please ensure the following are set:\n"
                "  - ALPACA_API_KEY\n"
                "  - ALPACA_SECRET\n"
                "  - SLACK_BOT_TOKEN\n"
                "  - PERSONAL_SLACK_CHANNEL_ID"
            )

        # Universe file
        self.universe_file = os.environ.get('UNIVERSE_FILE', 'system_long_short/ticker_universe.txt')

        # Trading mode
        self.paper = str_to_bool(os.environ.get('PAPER_TRADING', 'True'))

        # Risk parameters
        self.risk_per_unit = float(os.environ.get('RISK_PER_UNIT', '0.001'))

        # Order margins
        self.max_slippage = float(os.environ.get('MAX_SLIPPAGE', '0.005'))

        # Trading flags
        self.enable_longs = str_to_bool(os.environ.get('ENABLE_LONGS', 'True'))
        self.enable_shorts = str_to_bool(os.environ.get('ENABLE_SHORTS', 'True'))
        self.enable_system1 = str_to_bool(os.environ.get('ENABLE_SYSTEM1', 'True'))
        self.enable_system2 = str_to_bool(os.environ.get('ENABLE_SYSTEM2', 'False'))
        self.check_shortability = str_to_bool(os.environ.get('CHECK_SHORTABILITY', 'True'))

        # Pyramiding behavior
        self.use_latest_n_for_pyramiding = str_to_bool(os.environ.get('USE_LATEST_N_FOR_PYRAMIDING', 'False'))

    def __repr__(self):
        """String representation of config (hiding secrets)"""
        return (
            f"TradingConfig(\n"
            f"  alpaca_key={'*' * 8},\n"
            f"  paper={self.paper},\n"
            f"  risk_per_unit={self.risk_per_unit},\n"
            f"  enable_longs={self.enable_longs},\n"
            f"  enable_shorts={self.enable_shorts},\n"
            f"  enable_system1={self.enable_system1},\n"
            f"  enable_system2={self.enable_system2},\n"
            f"  check_shortability={self.check_shortability},\n"
            f"  use_latest_n_for_pyramiding={self.use_latest_n_for_pyramiding}\n"
            f")"
        )


class BacktesterConfig:
    """Configuration for backtester (API keys only)"""

    def __init__(self, env_file: str = '.env'):
        """
        Load configuration from .env file

        Args:
            env_file: Path to .env file (default: '.env')
        """
        # Load .env file
        env_vars = load_env_file(env_file)

        # Update os.environ with .env values (but don't override existing env vars)
        for key, value in env_vars.items():
            if key not in os.environ:
                os.environ[key] = value

        # API Credentials
        self.alpaca_key = os.environ.get('ALPACA_PAPER_KEY')
        self.alpaca_secret = os.environ.get('ALPACA_PAPER_SECRET')

        # Validate required credentials
        if not all([self.alpaca_key, self.alpaca_secret]):
            raise ValueError(
                "Missing required backtester credentials. Please ensure the following are set:\n"
                "  - ALPACA_PAPER_KEY\n"
                "  - ALPACA_PAPER_SECRET"
            )

    def __repr__(self):
        """String representation of config (hiding secrets)"""
        return f"BacktesterConfig(alpaca_key={'*' * 8})"
