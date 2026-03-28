#!/usr/bin/env python3
"""
HealthAI — Entry point
Run: streamlit run main.py
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Re-export the streamlit app
exec(open(os.path.join(os.path.dirname(__file__), "frontend", "app.py")).read())
