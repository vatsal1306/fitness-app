start:
	tmux new-session -d "python -m uvicorn src.app:app --port=8000 --host=0.0.0.0"

stop:
	tmux kill-server

run:
	python -m uvicorn src.app:app --port=8000 --host=0.0.0.0