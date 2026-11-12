from app import app, socketio, monitoring_loop

socketio.start_background_task(monitoring_loop)
