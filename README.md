# Installation

	python3 -m venv workdir
	source workdir/bin/activate
	pip install -r requirements.txt
	docker run -p 8050:8050 scrapinghub/splash # sorry, js parsing required for apec :\
	python3 sachajob.txt
