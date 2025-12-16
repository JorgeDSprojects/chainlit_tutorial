from operator import itemgetter
import os
import ollama
import subprocess
import threading
import requests
import asyncio

from dotenv import load_dotenv
from typing import Dict, Optional

import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

from chainlit.types import ThreadDict
import chainlit as cl

def _ollama():
    os.environ['OLLAMA_HOST'] = 'localhost:11434/v1'
    os.environ['OLLAMA_ORIGINS'] = '*'
    subprocess.Popen(['ollama', 'serve'])


def start_ollama():
    thread = threading.Thread(target=_ollama)
    thread.daemon = True
    thread.start()


@cl.on_chat_start
async def on_chat_start():
    start_ollama()
    cl.user_session.set('chat_history', [])

