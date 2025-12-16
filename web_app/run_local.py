"""
Advanced Computing Team Collaboration Swarm - Web App
This script runs the Streamlit web app locally for development and testing.
"""

import os
import streamlit as st
import sys
import argparse

def run_app():
    """Run the Streamlit app locally"""
    print("Starting Streamlit app...")
    os.system("streamlit run app.py")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Advanced Computing Team Collaboration Swarm web app locally")
    args = parser.parse_args()
    run_app()