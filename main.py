"""
main.py — Entry point. Starts the simulation engine in a background
thread, then starts the Flask + SocketIO web server in the main thread.

Run with: python main.py
On Replit: this is the file the Run button should execute.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from simulation import engine
from web.app import create_app


def main():
    print("=" * 60)
    print("  WORLD SIMULATION")
    print("=" * 60)
    print(f"  Tick: {config.SIM_MINUTES_PER_TICK} sim minutes / real second")
    print(f"  1 sim year ≈ {config.SIM_MINUTES_PER_YEAR / config.SIM_MINUTES_PER_TICK / 60:.1f} real minutes")
    print(f"  Dashboard will be available on port {config.FLASK_PORT}")
    if not config.DISCORD_WEBHOOK_URL:
        print("  NOTE: DISCORD_WEBHOOK_URL is not set — yearly chronicles will only")
        print("        be visible on the /chronicle web page, not posted to Discord.")
        print("        Set it in Replit Secrets to enable Discord updates.")
    print("=" * 60)

    engine.start_background_thread()

    app, socketio = create_app()
    socketio.run(app, host=config.FLASK_HOST, port=config.FLASK_PORT,
                 debug=False, use_reloader=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
