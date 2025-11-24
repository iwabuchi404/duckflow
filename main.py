#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.core import DuckAgent

from logging.handlers import RotatingFileHandler
from rich.traceback import install

# Install rich traceback handler
install(show_locals=False)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            "duckflow_v4.log", 
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        ),
        logging.StreamHandler(sys.stdout)
    ]
)
# Set external libs to WARNING to reduce noise
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

import argparse
from companion.tools.file_ops import file_ops

async def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Duckflow v4 Agent")
    parser.add_argument("--dir", type=str, default=".", help="Working directory for the agent")
    parser.add_argument("--debug-context", type=str, choices=["console", "file"], help="Debug: Output context messages")
    args = parser.parse_args()
    
    # Set workspace
    file_ops.set_workspace_root(args.dir)
    
    agent = DuckAgent(debug_context_mode=args.debug_context)
    await agent.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
